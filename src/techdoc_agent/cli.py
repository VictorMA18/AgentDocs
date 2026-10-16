"""Chat por consola para desarrollo: ``python -m techdoc_agent.cli``."""

from __future__ import annotations

import uuid

from techdoc_agent.core.agent import Agent, AgentResult
from techdoc_agent.core.llm import ClaudeCliClient, LLMError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.tools import ToolRegistry, toy_tools

AYUDA = "Comandos: /nuevo (reinicia la conversación), /salir"


def build_agent() -> Agent:
    return Agent(ClaudeCliClient(), ToolRegistry(toy_tools()), Memory())


def mostrar(result: AgentResult) -> None:
    print(f"\n{result.text}\n")
    for t in result.tool_calls:
        estado = "ERROR" if t.is_error else "ok"
        print(f"  · {t.name}({t.args}) → {estado} [{t.duration_ms} ms]")
    print(f"  [{result.iterations} paso(s), {result.input_tokens} tokens entrada, "
          f"{result.output_tokens} salida]\n")


def main() -> None:
    agent = build_agent()
    session_id = uuid.uuid4().hex[:8]
    print(f"TechDoc Agent (sesión {session_id}). {AYUDA}")
    while True:
        try:
            line = input("tú> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line == "/salir":
            break
        if line == "/nuevo":
            agent.memory.clear(session_id)
            print("Conversación reiniciada.")
            continue
        try:
            mostrar(agent.run(session_id, line))
        except LLMError as exc:
            print(f"\n[error del LLM] {exc}\n")


if __name__ == "__main__":
    main()
