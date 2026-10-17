"""Tests del comando /ingestar y del cableado de la CLI."""

from pathlib import Path

from fakes import FakeLLMClient, HashingEmbedder, final

from techdoc_agent.cli import build_agent, ingestar
from techdoc_agent.rag.store_json import JsonVectorStore


def make(tmp_path: Path) -> tuple[JsonVectorStore, HashingEmbedder]:
    return JsonVectorStore(tmp_path / "idx"), HashingEmbedder()


def test_ingest_file_and_dir(tmp_path: Path) -> None:
    store, emb = make(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\ntexto a", encoding="utf-8")
    (docs / "b.xyz").write_text("no permitido", encoding="utf-8")
    out = ingestar(str(docs), store, emb)
    assert "indexado a.md: 1 fragmentos" in out and "omitido b.xyz" in out
    assert "1 documento(s)" in out
    assert "indexado a.md" in ingestar(str(docs / "a.md"), store, emb)  # idempotente
    assert store.count() == 1


def test_ingest_errors_are_messages_not_exceptions(tmp_path: Path) -> None:
    store, emb = make(tmp_path)
    assert ingestar(str(tmp_path / "nada"), store, emb).startswith("No existe")
    bad = tmp_path / "x.xyz"
    bad.write_text("x", encoding="utf-8")
    assert ingestar(str(bad), store, emb).startswith("No se pudo indexar")


def test_build_agent_uses_skill_prompt_and_rag_tools(tmp_path: Path) -> None:
    store, emb = make(tmp_path)
    llm = FakeLLMClient([final("hola")])
    agent = build_agent(llm, store, emb)
    assert "<skill nombre=\"documentacion-tecnica\">" in agent.system_prompt
    assert {s.name for s in agent.tools.specs()} == {
        "buscar_documentos", "listar_documentos", "generar_diagrama", "generar_requisitos"}
