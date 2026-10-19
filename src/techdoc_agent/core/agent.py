"""Bucle del agente: LLM → herramientas → LLM … hasta una respuesta final.

El LLM, las herramientas y la memoria llegan por el constructor, así los
tests usan un LLM falso. Cada paso se registra con ``log_event``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from techdoc_agent import config
from techdoc_agent.core.llm import LLMClient, LLMError, LLMProtocolError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.prompts import with_summary
from techdoc_agent.core.summarizer import summarize
from techdoc_agent.core.tools import ToolRegistry, ToolResult, format_tool_results
from techdoc_agent.logging_setup import log_event

DEFAULT_SYSTEM_PROMPT = (
    "Eres un asistente útil y conciso. Responde en el idioma del usuario. "
    "Usa las herramientas disponibles cuando necesites un dato que puedan darte "
    "y no inventes resultados."
)


@dataclass(frozen=True)
class ToolTrace:
    """Registro de una herramienta ejecutada durante el turno."""

    name: str
    args: dict[str, Any]
    is_error: bool
    duration_ms: int
    result: str = ""  # texto que devolvió la herramienta (lo usan los adaptadores, p. ej. para artefactos)


@dataclass
class AgentResult:
    text: str
    tool_calls: list[ToolTrace] = field(default_factory=list)
    iterations: int = 0
    truncated: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


def _ms(start: float) -> int:
    return round((perf_counter() - start) * 1000)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        memory: Memory,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_iterations: int | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations or config.settings.max_agent_iterations

    def _maybe_compact(self, session_id: str) -> None:
        """Si el historial es grande, resume los turnos antiguos (no rompe el turno si falla)."""
        keep = config.settings.memory_keep_turns
        if (self.memory.turn_count(session_id) <= keep
                or self.memory.estimated_tokens(session_id) <= config.settings.memory_max_tokens):
            return
        started = perf_counter()
        old = self.memory.old_messages(session_id, keep)
        chars_before = sum(len(m["content"]) for m in self.memory.get(session_id))
        try:
            summary = summarize(self.llm, self.memory.summary(session_id), old)
        except LLMError as exc:  # se reintenta en el siguiente turno
            log_event(session=session_id, event="memory_compact_error", error=str(exc))
            return
        turns_before = self.memory.turn_count(session_id)
        self.memory.compact(session_id, summary, keep)
        chars_after = sum(len(m["content"]) for m in self.memory.get(session_id))
        log_event(session=session_id, event="memory_compacted",
                  turns_summarized=turns_before - self.memory.turn_count(session_id),
                  chars_before=chars_before, chars_after=chars_after,
                  summary_chars=len(summary), duration_ms=_ms(started))

    def run(self, session_id: str, user_message: str) -> AgentResult:
        try:
            return self._run(session_id, user_message)
        finally:  # también tras un error o el tope de iteraciones: el disco refleja el estado final
            self._persist(session_id)

    def _persist(self, session_id: str) -> None:
        """Guarda la memoria; si el disco falla, la conversación sigue en RAM."""
        try:
            self.memory.save(session_id)
        except OSError as exc:
            log_event(session=session_id, event="memory_save_error", error=str(exc))

    def _run(self, session_id: str, user_message: str) -> AgentResult:
        self._maybe_compact(session_id)
        history = self.memory.get(session_id)
        self.memory.mark_turn(session_id)
        history.append({"role": "user", "content": user_message})
        log_event(session=session_id, event="user_message", chars=len(user_message))

        result = AgentResult(text="")
        for iteration in range(1, self.max_iterations + 1):
            result.iterations = iteration
            started = perf_counter()
            try:
                system = with_summary(self.system_prompt, self.memory.summary(session_id))
                reply = self.llm.complete(system, history, self.tools.specs())
            except LLMProtocolError as exc:
                # Recuperable: se lo devolvemos al modelo para que se corrija.
                log_event(session=session_id, iter=iteration, event="llm_protocol_error",
                          error=str(exc), duration_ms=_ms(started))
                history.append({"role": "assistant", "content": exc.raw or "(sin respuesta válida)"})
                history.append({"role": "user", "content": (
                    f"Error de protocolo: {exc} Responde con el objeto JSON del protocolo."
                )})
                continue
            except LLMError as exc:
                # No recuperable: deshacemos el turno para no dejar dos 'user' seguidos.
                log_event(session=session_id, iter=iteration, event="llm_error", error=str(exc))
                self.memory.drop_last_turn(session_id)
                raise

            result.input_tokens += reply.input_tokens
            result.output_tokens += reply.output_tokens
            log_event(session=session_id, iter=iteration, event="llm_response",
                      tool_calls=len(reply.tool_calls), input_tokens=reply.input_tokens,
                      output_tokens=reply.output_tokens, duration_ms=_ms(started))
            history.append({"role": "assistant", "content": reply.raw})

            if not reply.tool_calls:
                result.text = reply.text or ""
                return result

            # Un turno puede pedir varias herramientas: se responden todas en un solo mensaje.
            tool_results: list[ToolResult] = []
            for call in reply.tool_calls:
                tool_started = perf_counter()
                content, is_error = self.tools.dispatch(call.name, call.args)
                duration = _ms(tool_started)
                tool_results.append(ToolResult(call.id, content, is_error))
                result.tool_calls.append(ToolTrace(call.name, call.args, is_error, duration, content))
                log_event(session=session_id, iter=iteration, event="tool_call", tool=call.name,
                          args=call.args, duration_ms=duration, is_error=is_error,
                          result_chars=len(content))
            history.append({"role": "user", "content": format_tool_results(tool_results)})

        result.truncated = True
        result.text = (
            f"Alcancé el límite de {self.max_iterations} pasos sin llegar a una respuesta final."
        )
        history.append({"role": "assistant", "content": json.dumps(
            {"accion": "responder", "texto": result.text}, ensure_ascii=False)})
        log_event(session=session_id, event="max_iterations", limit=self.max_iterations)
        return result
