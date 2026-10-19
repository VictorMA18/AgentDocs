"""Chat por consola para desarrollo: ``python -m techdoc_agent.cli``."""

from __future__ import annotations

import uuid
from pathlib import Path

from techdoc_agent.core.agent import Agent, AgentResult
from techdoc_agent.core.llm import ClaudeCliClient, LLMClient, LLMError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.prompts import build_system_prompt
from techdoc_agent.core.skills import load_skill
from techdoc_agent.core.tools import ToolRegistry
from techdoc_agent.core.tools_outputs import output_tools
from techdoc_agent.core.tools_rag import rag_tools
from techdoc_agent.rag.embeddings import Embedder, SentenceTransformerEmbedder
from techdoc_agent.rag.ingest import ingest_dir, ingest_file
from techdoc_agent.rag.store import VectorStore
from techdoc_agent.rag.factory import build_store

AYUDA = "Comandos: /ingestar <ruta> (indexa un archivo o carpeta), /nuevo (reinicia), /salir"


def build_agent(llm: LLMClient, store: VectorStore, embedder: Embedder) -> Agent:
    """Une el LLM, las herramientas RAG y el system prompt (reglas fijas + skill activa)."""
    prompt = build_system_prompt(load_skill())
    return Agent(llm, ToolRegistry([*rag_tools(store, embedder), *output_tools()]), Memory(), prompt)


def ingestar(ruta: str, store: VectorStore, embedder: Embedder) -> str:
    """Comando ``/ingestar``: indexa un archivo o carpeta y devuelve un resumen."""
    path = Path(ruta).expanduser()
    if not path.exists():
        return f"No existe: {path}"
    lines: list[str] = []
    try:
        if path.is_dir():
            report = ingest_dir(path, store, embedder)
            reports, skipped = report.ingested, report.skipped
        else:
            reports, skipped = [ingest_file(path, store, embedder)], []
    except ValueError as exc:
        return f"No se pudo indexar: {exc}"
    for r in reports:
        lines.append(f"indexado {r.source}: {r.chunks} fragmentos")
        lines.extend(f"  aviso: {w}" for w in r.warnings)
    lines.extend(f"omitido {name}: {reason}" for name, reason in skipped)
    lines.append(f"Índice: {store.count()} fragmentos en {len(store.list_sources())} documento(s)")
    return "\n".join(lines)


def mostrar(result: AgentResult) -> None:
    print(f"\n{result.text}\n")
    for t in result.tool_calls:
        estado = "ERROR" if t.is_error else "ok"
        print(f"  · {t.name}({t.args}) → {estado} [{t.duration_ms} ms]")
    print(f"  [{result.iterations} paso(s), {result.input_tokens} tokens entrada, "
          f"{result.output_tokens} salida]\n")


def main() -> None:
    print("Cargando modelo de embeddings…")
    embedder = SentenceTransformerEmbedder()
    store = build_store()
    agent = build_agent(ClaudeCliClient(), store, embedder)
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
        if line == "/ingestar" or line.startswith("/ingestar "):
            ruta = line.removeprefix("/ingestar").strip()
            print(ingestar(ruta, store, embedder) if ruta else "Uso: /ingestar <ruta>")
            continue
        try:
            mostrar(agent.run(session_id, line))
        except LLMError as exc:
            print(f"\n[error del LLM] {exc}\n")


if __name__ == "__main__":
    main()
