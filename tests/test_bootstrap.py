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


def test_outputs_dir_is_where_the_output_tools_save(tmp_path: Path) -> None:
    store, emb = JsonVectorStore(tmp_path / "idx"), HashingEmbedder()
    agent = build_agent(FakeLLMClient([final("x")]), store, emb, outputs_dir=tmp_path / "salidas")
    text, is_error = agent.tools.dispatch("generar_diagrama", {
        "tipo": "flujo", "titulo": "Prueba", "codigo": "flowchart TD\n    A[Inicio] --> B[Fin]"})
    assert not is_error and len(list((tmp_path / "salidas").glob("*.mmd"))) == 1
