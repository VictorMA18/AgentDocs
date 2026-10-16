"""Cliente LLM: interfaz ``LLMClient`` e implementación sobre el CLI de Claude Code.

El CLI (``claude -p``) se usa como una función "texto → texto", sin sus
herramientas propias. Las herramientas del agente se piden con un protocolo
JSON definido aquí (ver docs/04 y ADR-008):

    {"accion": "herramientas", "llamadas": [{"id": "c1", "nombre": "...", "args": {...}}]}
    {"accion": "responder", "texto": "..."}

``--json-schema`` obliga al modelo a devolver esa forma; el resto de la
coherencia se valida en ``parse_output``.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Protocol

from techdoc_agent import config
from techdoc_agent.core.tools import ToolSpec

# Mensaje del historial: {"role": "user" | "assistant", "content": "..."}
Message = dict[str, str]

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accion": {"type": "string", "enum": ["herramientas", "responder"]},
        "llamadas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "nombre": {"type": "string"},
                    "args": {"type": "object"},
                },
                "required": ["id", "nombre", "args"],
            },
        },
        "texto": {"type": "string"},
    },
    "required": ["accion"],
}

_PROTOCOL_RULES = """\
## Protocolo de respuesta
Respondes SIEMPRE con un objeto JSON de una de estas dos formas:
- Para usar herramientas: {"accion": "herramientas", "llamadas": [{"id": "c1", "nombre": "<herramienta>", "args": {...}}]}
  Puedes pedir varias llamadas a la vez; cada una con un id único dentro del mensaje.
- Para responder al usuario: {"accion": "responder", "texto": "<respuesta final>"}
Los resultados de las herramientas llegan después como bloques <resultado_herramienta id="..." error="true|false">.
Si un resultado tiene error="true", corrige los argumentos o explica el problema al usuario.
No inventes resultados de herramientas: si necesitas un dato que una herramienta puede dar, pídelo."""


class LLMError(Exception):
    """Fallo al llamar al LLM (CLI ausente, timeout, error del proceso)."""


class LLMProtocolError(LLMError):
    """El modelo respondió, pero no con el protocolo esperado (recuperable)."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class LLMReply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    raw: str = ""  # lo que se guarda en el historial como mensaje del asistente


class LLMClient(Protocol):
    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> LLMReply: ...


def _validate(structured: Any, raw: str) -> tuple[str | None, list[ToolCall]]:
    """Comprueba la coherencia del protocolo y devuelve ``(texto, llamadas)``."""
    if not isinstance(structured, dict):
        raise LLMProtocolError("La salida del modelo no es un objeto JSON.", raw)

    accion = structured.get("accion")
    if accion == "responder":
        texto = structured.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise LLMProtocolError("accion 'responder' sin 'texto'.", raw)
        return texto, []

    if accion == "herramientas":
        llamadas = structured.get("llamadas")
        if not isinstance(llamadas, list) or not llamadas:
            raise LLMProtocolError("accion 'herramientas' sin 'llamadas'.", raw)
        calls: list[ToolCall] = []
        for item in llamadas:
            ok = (
                isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and isinstance(item.get("nombre"), str)
                and isinstance(item.get("args"), dict)
            )
            if not ok:
                raise LLMProtocolError(
                    "Cada llamada necesita 'id', 'nombre' (texto) y 'args' (objeto).", raw
                )
            calls.append(ToolCall(item["id"], item["nombre"], item["args"]))
        return None, calls

    raise LLMProtocolError(f"'accion' desconocida: {accion!r}.", raw)


def parse_output(stdout: str) -> LLMReply:
    """Convierte la salida JSON del CLI en un ``LLMReply`` validado."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LLMError(f"La salida del CLI no es JSON: {exc}") from None
    if not isinstance(data, dict):
        raise LLMError("La salida del CLI no es un objeto JSON.")
    if data.get("is_error"):
        raise LLMError(f"El CLI devolvió un error: {data.get('result', '')!s:.300}")

    structured = data.get("structured_output")
    result_text = str(data.get("result", ""))
    if structured is None:
        raise LLMProtocolError("El modelo no devolvió salida estructurada.", result_text)
    raw = json.dumps(structured, ensure_ascii=False)

    text, calls = _validate(structured, raw)
    usage = data.get("usage") or {}
    input_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    return LLMReply(
        text=text,
        tool_calls=calls,
        input_tokens=input_tokens,
        output_tokens=usage.get("output_tokens", 0),
        raw=raw,
    )


class ClaudeCliClient:
    """``LLMClient`` que ejecuta ``claude -p`` como subproceso."""

    def __init__(
        self,
        model: str | None = None,
        cli_path: str | None = None,
        timeout_s: int | None = None,
    ) -> None:
        s = config.settings
        self.model = model or s.model
        self.cli_path = cli_path or s.claude_cli_path
        self.timeout_s = timeout_s or s.llm_timeout_s

    @staticmethod
    def _build_system(system: str, tools: list[ToolSpec]) -> str:
        parts = [system, _PROTOCOL_RULES]
        if tools:
            catalogo = json.dumps(
                [
                    {"nombre": t.name, "descripcion": t.description, "args_schema": t.input_schema}
                    for t in tools
                ],
                ensure_ascii=False,
                indent=2,
            )
            parts.append(f"## Herramientas disponibles\n{catalogo}")
        else:
            parts.append("No hay herramientas disponibles: usa siempre accion 'responder'.")
        return "\n\n".join(parts)

    @staticmethod
    def _render_messages(messages: list[Message]) -> str:
        """Transcripción del historial; el CLI no guarda estado entre llamadas."""
        etiquetas = {"user": "usuario", "assistant": "asistente"}
        bloques = [f"[{etiquetas[m['role']]}]\n{m['content']}" for m in messages]
        bloques.append("[asistente]\n(responde con el objeto JSON del protocolo)")
        return "\n\n".join(bloques)

    def _command(self, system: str, tools: list[ToolSpec]) -> list[str]:
        return [
            self.cli_path,
            "-p",
            "--model", self.model,
            "--tools", "",
            "--no-session-persistence",
            "--output-format", "json",
            # Sin esto cada llamada arrastra ~38k tokens de contexto de Claude Code.
            "--setting-sources", "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--system-prompt", self._build_system(system, tools),
            "--json-schema", json.dumps(OUTPUT_SCHEMA),
        ]

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> LLMReply:
        try:
            proc = subprocess.run(
                self._command(system, tools),
                input=self._render_messages(messages),  # por stdin: sin límite de argv
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                # Fuera del proyecto, para que el CLI no cargue nuestro CLAUDE.md.
                cwd=tempfile.gettempdir(),
            )
        except FileNotFoundError:
            raise LLMError(f"No se encontró el CLI {self.cli_path!r} (CLAUDE_CLI_PATH).") from None
        except subprocess.TimeoutExpired:
            raise LLMError(f"El CLI superó el tiempo máximo ({self.timeout_s} s).") from None
        if proc.returncode != 0:
            raise LLMError(f"El CLI terminó con código {proc.returncode}: {proc.stderr.strip()[:300]}")
        return parse_output(proc.stdout)
