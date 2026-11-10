"""El agente con las herramientas RAG reales y un LLM con guion."""

import json
from pathlib import Path

import pytest
from fakes import FakeLLMClient, HashingEmbedder, calls, final

from techdoc_agent.core.agent import Agent
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.tools import ToolRegistry
from techdoc_agent.core.tools_rag import NO_RESULTS, rag_tools
from techdoc_agent.rag.ingest import ingest_file
from techdoc_agent.rag.store_json import JsonVectorStore

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_docs" / "taskflow.md"


def make(tmp_path: Path, script: list) -> tuple[Agent, FakeLLMClient]:
    emb = HashingEmbedder()
    store = JsonVectorStore(tmp_path / "idx")
    ingest_file(SAMPLE, store, emb)
    llm = FakeLLMClient(script)
    return Agent(llm, ToolRegistry(rag_tools(store, emb)), Memory()), llm


def test_greeting_uses_no_tools_and_no_search_happens_before_the_llm(tmp_path: Path) -> None:
    agent, llm = make(tmp_path, [final("¡Hola!")])
    result = agent.run("s", "hola")
    assert result.tool_calls == [] and len(llm.seen) == 1
    assert llm.seen[0] == [{"role": "user", "content": "hola"}]  # nada de contexto previo


def test_question_triggers_search_and_cited_answer(tmp_path: Path) -> None:
    agent, llm = make(tmp_path, [
        calls(("c1", "buscar_documentos", {"query": "reintentos max_retries"})),
        final("Se configura con max_retries [taskflow.md#3]."),
    ])
    result = agent.run("s", "¿cómo configuro los reintentos?")
    assert [t.name for t in result.tool_calls] == ["buscar_documentos"]
    tool_msg = llm.seen[1][-1]["content"]
    assert tool_msg.startswith('<resultado_herramienta id="c1" error="false"><documento ')
    assert "[taskflow.md#" in result.text


def test_compound_question_logs_two_searches(tmp_path: Path, logs_dir: Path) -> None:
    agent, _ = make(tmp_path, [
        calls(("c1", "buscar_documentos", {"query": "concurrencia del worker"})),
        calls(("c2", "buscar_documentos", {"query": "reintentos"})),
        final("listo"),
    ])
    agent.run("s", "concurrencia y reintentos")
    events = [json.loads(line) for f in logs_dir.glob("agent-*.jsonl") for line in f.read_text().splitlines()]
    searches = [e for e in events if e["event"] == "tool_call" and e["tool"] == "buscar_documentos"]
    assert [e["args"]["query"] for e in searches] == ["concurrencia del worker", "reintentos"]


def test_no_results_text_reaches_the_model(tmp_path: Path) -> None:
    agent, llm = make(tmp_path, [
        calls(("c1", "buscar_documentos", {"query": "zzzz qqqq xxxx"})),
        final("No aparece en la documentación."),
    ])
    agent.run("s", "¿y Kubernetes?")
    assert NO_RESULTS in llm.seen[1][-1]["content"]


def test_invalid_top_k_comes_back_as_error_and_model_recovers(tmp_path: Path) -> None:
    agent, llm = make(tmp_path, [
        calls(("c1", "buscar_documentos", {"query": "reintentos", "top_k": 50})),
        calls(("c2", "buscar_documentos", {"query": "reintentos", "top_k": 5})),
        final("ok"),
    ])
    result = agent.run("s", "x")
    assert [t.is_error for t in result.tool_calls] == [True, False]
    assert 'error="true"' in llm.seen[1][-1]["content"]
