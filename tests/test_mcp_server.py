"""Servidor MCP en proceso: se llama a las herramientas con el cliente del SDK y un núcleo falso."""

import asyncio
import dataclasses
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeLLMClient, HashingEmbedder, calls, final
from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from techdoc_agent import config
from techdoc_agent.bootstrap import build_agent
from techdoc_agent.core.llm import LLMError, LLMReply
from techdoc_agent.mcp_server import create_server
from techdoc_agent.rag.ingest import ingest_file
from techdoc_agent.rag.store_json import JsonVectorStore

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_docs" / "taskflow.md"


@dataclass
class Env:
    server: MCPServer
    llm: FakeLLMClient
    store: JsonVectorStore
    allowed: Path  # carpeta permitida para ingestar
    root: Path

    def call(self, name: str, args: dict[str, Any] | None = None) -> tuple[bool, str]:
        """Llama a una herramienta y devuelve ``(is_error, texto)``."""
        async def run() -> tuple[bool, str]:
            async with Client(self.server) as client:
                result = await client.call_tool(name, args or {})
                return result.is_error, "".join(getattr(c, "text", "") for c in result.content)
        return asyncio.run(run())


@pytest.fixture
def make_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logs_dir: Path) -> Callable[..., Env]:
    allowed = tmp_path / "permitidos"
    allowed.mkdir()
    monkeypatch.setattr(config, "settings", dataclasses.replace(
        config.settings, allowed_ingest_dir=allowed, logs_dir=logs_dir, outputs_dir=tmp_path / "outputs"))

    def make(script: list[LLMReply | Exception] | None = None, indexed: bool = False) -> Env:
        llm, embedder = FakeLLMClient(script or []), HashingEmbedder()
        store = JsonVectorStore(tmp_path / "idx")
        if indexed:
            ingest_file(SAMPLE, store, embedder)
        server = create_server(build_agent(llm, store, embedder), store, embedder)
        return Env(server, llm, store, allowed, tmp_path)

    return make


# --- anuncio de herramientas ---


def test_server_announces_the_four_tools_with_descriptions(make_env: Callable[..., Env]) -> None:
    env = make_env()

    async def run():
        async with Client(env.server) as client:
            return (await client.list_tools()).tools

    tools = {t.name: t for t in asyncio.run(run())}
    assert set(tools) == {"buscar_documentos", "listar_documentos", "ingestar_documento", "preguntar_agente"}
    assert all(t.description and len(t.description) > 40 for t in tools.values())
    assert tools["buscar_documentos"].input_schema["required"] == ["query"]
    assert tools["preguntar_agente"].input_schema["required"] == ["pregunta"]


# --- buscar y listar (delegan en las herramientas del agente) ---


def test_list_documents_empty_and_populated(make_env: Callable[..., Env]) -> None:
    assert make_env().call("listar_documentos") == (False, "No hay documentos indexados.")
    is_error, text = make_env(indexed=True).call("listar_documentos")
    assert not is_error and text.startswith("- taskflow.md: ")


def test_search_returns_citable_fragments(make_env: Callable[..., Env]) -> None:
    is_error, text = make_env(indexed=True).call("buscar_documentos", {"query": "reintentos max_retries backoff"})
    assert not is_error and '<documento fuente="taskflow.md#' in text and "max_retries" in text


def test_search_source_filter_and_no_results(make_env: Callable[..., Env]) -> None:
    env = make_env(indexed=True)
    assert env.call("buscar_documentos", {"query": "reintentos", "source": "otro.md"}) == (
        False, "Sin resultados relevantes para esa consulta.")
    assert env.call("buscar_documentos", {"query": "zzzz qqqq xxxx"})[1] == (
        "Sin resultados relevantes para esa consulta.")


@pytest.mark.parametrize("args,reason", [
    ({"query": "reintentos", "top_k": 99}, "top_k debe ser un entero entre 1 y 10"),
    ({"query": "   "}, "query debe ser un texto no vacío"),
])
def test_invalid_search_arguments_show_the_real_reason(make_env: Callable[..., Env], args: dict, reason: str) -> None:
    is_error, text = make_env(indexed=True).call("buscar_documentos", args)
    assert is_error and reason in text  # no el mensaje enmascarado del SDK


def test_missing_required_argument_is_an_error(make_env: Callable[..., Env]) -> None:
    assert make_env().call("buscar_documentos", {})[0] is True


# --- ingestar ---


def test_ingest_inside_the_allowed_directory(make_env: Callable[..., Env]) -> None:
    env = make_env()
    (env.allowed / "nota.md").write_text("# Nota\n\nTexto sobre reintentos de prueba.", encoding="utf-8")
    assert env.call("ingestar_documento", {"ruta": "nota.md"}) == (False, "indexado nota.md: 1 fragmentos")
    assert env.call("ingestar_documento", {"ruta": str(env.allowed / "nota.md")})[0] is False  # ruta absoluta dentro
    assert env.store.count() == 1  # y reindexar no duplica
    assert "nota.md" in env.call("listar_documentos")[1]


@pytest.mark.parametrize("ruta", ["../fuera.md", "sub/../../fuera.md", "FUERA_ABS", "/etc/passwd"])
def test_ingest_rejects_paths_outside(make_env: Callable[..., Env], ruta: str) -> None:
    env = make_env()
    outside = env.root / "fuera.md"
    outside.write_text("# Secreto\n\ncontenido fuera de la carpeta", encoding="utf-8")
    ruta = str(outside) if ruta == "FUERA_ABS" else ruta
    is_error, text = env.call("ingestar_documento", {"ruta": ruta})
    assert is_error and "Ruta no permitida" in text and str(env.root) not in text
    assert env.store.count() == 0


def test_ingest_rejects_symlink_pointing_outside(make_env: Callable[..., Env]) -> None:
    env = make_env()
    (env.root / "secreto.md").write_text("# S\n\nsecreto", encoding="utf-8")
    os.symlink(env.root / "secreto.md", env.allowed / "enlace.md")
    is_error, text = env.call("ingestar_documento", {"ruta": "enlace.md"})
    assert is_error and "Ruta no permitida" in text and env.store.count() == 0


def test_ingest_missing_file_and_bad_extension(make_env: Callable[..., Env]) -> None:
    env = make_env()
    assert "No se encontró" in env.call("ingestar_documento", {"ruta": "no-existe.md"})[1]
    (env.allowed / "virus.exe").write_bytes(b"MZ")
    is_error, text = env.call("ingestar_documento", {"ruta": "virus.exe"})
    assert is_error and "Extensión no permitida" in text and env.store.count() == 0


def test_ingest_directory_is_not_a_file(make_env: Callable[..., Env]) -> None:
    env = make_env()
    (env.allowed / "carpeta.md").mkdir()
    assert env.call("ingestar_documento", {"ruta": "carpeta.md"})[0] is True
    assert env.call("ingestar_documento", {"ruta": ""})[0] is True


# --- preguntar al agente completo ---


def test_ask_agent_uses_its_own_tools_and_returns_the_cited_answer(make_env: Callable[..., Env]) -> None:
    env = make_env([
        calls(("c1", "buscar_documentos", {"query": "reintentos max_retries"})),
        final("Se configura con max_retries [taskflow.md#5]."),
    ], indexed=True)
    is_error, text = env.call("preguntar_agente", {"pregunta": "¿cómo configuro los reintentos?"})
    assert not is_error and text == "Se configura con max_retries [taskflow.md#5]."
    assert '<documento fuente="taskflow.md#' in env.llm.seen[1][-1]["content"]  # buscó por dentro


def test_ask_agent_remembers_per_session(make_env: Callable[..., Env]) -> None:
    env = make_env([final("uno"), final("dos"), final("tres")])
    env.call("preguntar_agente", {"pregunta": "primera", "session_id": "sesion-a"})
    env.call("preguntar_agente", {"pregunta": "segunda", "session_id": "sesion-a"})
    env.call("preguntar_agente", {"pregunta": "otra", "session_id": "sesion-b"})
    assert env.llm.seen[1][0]["content"] == "primera"  # la misma sesión ve lo anterior
    assert env.llm.seen[2] == [{"role": "user", "content": "otra"}]  # otra sesión, no


def test_ask_agent_validation(make_env: Callable[..., Env]) -> None:
    env = make_env()
    for args in ({"pregunta": "  "}, {"pregunta": "x" * 8001}, {"pregunta": "hola", "session_id": "../x"}):
        is_error, text = env.call("preguntar_agente", args)
        assert is_error and "Error executing tool" in text
    assert env.llm.seen == []  # nada llegó al modelo


def test_ask_agent_hides_llm_failure_details(make_env: Callable[..., Env]) -> None:
    env = make_env([LLMError("claude falló en /home/usuario/secreto")])
    is_error, text = env.call("preguntar_agente", {"pregunta": "hola"})
    assert is_error and "fallo del modelo" in text and "secreto" not in text


# --- frontera de arquitectura ---


def test_mcp_server_is_a_thin_adapter() -> None:
    """No importa la API web y solo toca el núcleo por sus puntos de entrada públicos."""
    import re

    import techdoc_agent.mcp_server as module

    text = Path(module.__file__).read_text(encoding="utf-8")
    imports = set(re.findall(r"^from (techdoc_agent[\w.]*) import", text, flags=re.M))
    assert imports == {
        "techdoc_agent", "techdoc_agent.bootstrap", "techdoc_agent.core.agent", "techdoc_agent.core.llm",
        "techdoc_agent.core.storage", "techdoc_agent.core.tools", "techdoc_agent.core.tools_rag",
        "techdoc_agent.rag.embeddings", "techdoc_agent.rag.factory", "techdoc_agent.rag.ingest",
        "techdoc_agent.rag.store"}


# --- concurrencia ---


def test_parallel_calls_are_serialized_and_none_fails(make_env: Callable[..., Env]) -> None:
    """Un cliente puede lanzar varias llamadas a la vez: los turnos del agente no deben solaparse."""
    import threading
    import time

    state = {"running": 0, "max": 0}
    guard = threading.Lock()

    class SlowLLM:
        def complete(self, system, messages, tools):  # noqa: ANN001
            with guard:
                state["running"] += 1
                state["max"] = max(state["max"], state["running"])
            time.sleep(0.15)
            with guard:
                state["running"] -= 1
            return final(f"respuesta a: {messages[-1]['content']}")

    env = make_env(indexed=True)
    store, embedder = env.store, HashingEmbedder()
    server = create_server(build_agent(SlowLLM(), store, embedder), store, embedder)

    async def run() -> list[tuple[bool, str]]:
        async with Client(server) as client:
            jobs = [client.call_tool("preguntar_agente", {"pregunta": f"pregunta {i}", "session_id": f"sesion-{i}"})
                    for i in range(4)]
            jobs += [client.call_tool("listar_documentos", {}), client.call_tool("buscar_documentos", {"query": "reintentos"})]
            results = await asyncio.gather(*jobs)
            return [(r.is_error, r.content[0].text) for r in results]

    results = asyncio.run(run())
    assert not any(is_error for is_error, _ in results)
    assert [text for _, text in results[:4]] == [f"respuesta a: pregunta {i}" for i in range(4)]  # cada una la suya
    assert state["max"] == 1  # nunca dos turnos del agente a la vez
