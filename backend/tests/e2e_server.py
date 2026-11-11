"""Servidor de la API para las pruebas E2E del frontend (Playwright): núcleo real, LLM falso.

Arranca la misma ``create_app`` de producción con un LLM guionizado (sin tokens ni red) y el embedder
de hash de los tests (sin descargar modelos), todo en una carpeta temporal (``techdoc-e2e-*``).
No es un test de pytest (no empieza por ``test_``); lo lanza ``frontend/playwright.config.ts``:

    python tests/e2e_server.py        # desde backend/, puerto E2E_API_PORT (8001 por defecto)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# Playwright detiene el servidor sin darle ocasión de limpiar: se borran los restos de ejecuciones previas.
for _old in Path(tempfile.gettempdir()).glob("techdoc-e2e-*"):
    shutil.rmtree(_old, ignore_errors=True)

# La configuración se lee al importar techdoc_agent: el entorno se fija antes.
_TMP = Path(tempfile.mkdtemp(prefix="techdoc-e2e-"))
PORT = int(os.environ.get("E2E_API_PORT", "8001"))
FRONT = os.environ.get("E2E_FRONT_ORIGIN", "http://127.0.0.1:3100")
os.environ.update({
    "DATA_DIR": str(_TMP / "data"), "OUTPUTS_DIR": str(_TMP / "outputs"), "LOGS_DIR": str(_TMP / "logs"),
    "VECTOR_STORE": "json", "MERMAID_VALIDATE": "heuristic", "CORS_ORIGINS": FRONT,
    "LLM_PROVIDER": "claude",  # el LLM del agente es el de por defecto; gemini sale de la factoría
})
sys.path.insert(0, str(Path(__file__).parent))  # para importar fakes.py

import uvicorn  # noqa: E402
from fakes import HashingEmbedder  # noqa: E402

from techdoc_agent.api.app import create_app  # noqa: E402
from techdoc_agent.api.deps import conversations_dir  # noqa: E402
from techdoc_agent.bootstrap import build_agent  # noqa: E402
from techdoc_agent.core.llm import LLMReply, Message, ToolCall  # noqa: E402
from techdoc_agent.core.llm_factory import model_for  # noqa: E402
from techdoc_agent.core.memory import Memory  # noqa: E402
from techdoc_agent.core.tools import ToolSpec  # noqa: E402
from techdoc_agent.rag.store_json import JsonVectorStore  # noqa: E402

DIAGRAM = "sequenceDiagram\n    Usuario->>API: POST /login\n    API-->>Usuario: token JWT"


def _reply(text: str) -> LLMReply:
    return LLMReply(text=text, input_tokens=120, output_tokens=40,
                    raw=json.dumps({"accion": "responder", "texto": text}, ensure_ascii=False))


def _call(name: str, args: dict[str, str]) -> LLMReply:
    raw = json.dumps({"accion": "herramientas", "llamadas": [{"id": "c1", "nombre": name, "args": args}]},
                     ensure_ascii=False)
    return LLMReply(text=None, tool_calls=[ToolCall("c1", name, args)], input_tokens=100, output_tokens=20, raw=raw)


class ScriptedLLM:
    """Decide por el último mensaje: si pide un diagrama lo genera; si no, busca y responde citando.

    ``prefix`` marca qué proveedor respondió (``[gemini] …``); el de por defecto no lleva prefijo.
    """

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        last = str(messages[-1]["content"])
        question = next(str(m["content"]) for m in reversed(messages)
                        if m["role"] == "user" and not str(m["content"]).startswith("<resultado_herramienta"))
        wants_diagram = "diagrama" in question.lower()
        if not last.startswith("<resultado_herramienta"):
            if wants_diagram:
                return _call("generar_diagrama", {"tipo": "secuencia", "titulo": "Flujo de login", "codigo": DIAGRAM})
            return _call("buscar_documentos", {"query": question})
        if wants_diagram:
            return _reply(f"{self.prefix}He generado el diagrama de secuencia del login.")
        sources = sorted(set(re.findall(r"[\w-]+\.(?:md|txt)", last)))
        cite = f"Fuente: {sources[0]}" if sources else "No encontré fragmentos relevantes."
        return _reply(f"{self.prefix}Según la documentación, TaskFlow organiza el trabajo en tareas.\n\n"
                      f"```python\nprint('hola')\n```\n\n{cite}")


def providers() -> list[dict[str, object]]:
    """Los dos disponibles sin clave ni CLI reales, con los modelos de la configuración (los mismos
    que la API pone en ``llm`` de cada respuesta)."""
    return [{"id": p, "label": p.title(), "model": model_for(p), "available": True, "reason": None,
             "default": p == "claude"} for p in ("claude", "gemini")]


def build_app():  # noqa: ANN201 - FastAPI
    store, embedder = JsonVectorStore(_TMP / "data" / "index"), HashingEmbedder()
    agent = build_agent(ScriptedLLM(), store, embedder, Memory(conversations_dir()))
    gemini = ScriptedLLM("[gemini] ")
    return create_app(agent, store, embedder, llm_factory=lambda _provider: gemini, provider_status=providers)


if __name__ == "__main__":
    print(f"API E2E en http://127.0.0.1:{PORT} (datos en {_TMP}, CORS para {FRONT})", file=sys.stderr)
    try:
        uvicorn.run(build_app(), host="127.0.0.1", port=PORT, log_level="warning")
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
