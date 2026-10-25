"""Tests del comando /ingestar y del cableado de la CLI."""

from pathlib import Path

from fakes import HashingEmbedder

from techdoc_agent.cli import ingestar
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


def test_unknown_slash_command_is_detected_but_paths_and_known_commands_are_not() -> None:
    from techdoc_agent.cli import comando_desconocido

    assert comando_desconocido("/foo") == "/foo" and comando_desconocido("/Ingestar x") is None
    assert comando_desconocido("/foo bar baz") == "/foo"
    assert all(comando_desconocido(c) is None for c in ("/nuevo", "/salir", "/ingestar ruta.md"))
    assert comando_desconocido("/etc/hosts ¿qué es esto?") is None  # una ruta va al agente
    assert comando_desconocido("¿Qué hace /foo?") is None
