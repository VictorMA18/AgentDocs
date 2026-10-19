"""Test del ensamblado del agente."""

from pathlib import Path

from fakes import FakeLLMClient, HashingEmbedder, final

from techdoc_agent.bootstrap import build_agent
from techdoc_agent.rag.store_json import JsonVectorStore


def test_build_agent_uses_skill_prompt_and_rag_tools(tmp_path: Path) -> None:
    store, emb = JsonVectorStore(tmp_path / "idx"), HashingEmbedder()
    llm = FakeLLMClient([final("hola")])
    agent = build_agent(llm, store, emb)
    assert "<skill nombre=\"documentacion-tecnica\">" in agent.system_prompt
    assert {s.name for s in agent.tools.specs()} == {
        "buscar_documentos", "listar_documentos", "generar_diagrama", "generar_requisitos"}
