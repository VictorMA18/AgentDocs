"""Tests de ingesta y recuperación con un embedder falso (sin modelos)."""

import dataclasses
import json
from pathlib import Path

import pytest
from fakes import HashingEmbedder

from techdoc_agent import config
from techdoc_agent.rag.ingest import ingest_dir, ingest_file, main
from techdoc_agent.rag.retrieval import search
from techdoc_agent.rag.store_json import JsonVectorStore

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_docs"


@pytest.fixture(autouse=True)
def _isolated_logs(logs_dir: Path) -> None:
    """Los tests no escriben en ``logs/`` real."""


@pytest.fixture
def store(tmp_path: Path) -> JsonVectorStore:
    return JsonVectorStore(tmp_path / "index")


def test_ingest_sample_and_search_retries_in_top_3(store: JsonVectorStore) -> None:
    emb = HashingEmbedder()
    report = ingest_dir(SAMPLE_DIR, store, emb)
    assert [r.source for r in report.ingested] == ["taskflow.md"] and report.skipped == []
    assert store.count() == report.ingested[0].chunks > 3

    hits = search(store, emb, "reintentos", top_k=3)
    assert any(h.chunk.metadata["section"] == "Reintentos" for h in hits)
    assert hits[0].chunk.source == "taskflow.md"


def test_reingest_does_not_duplicate(store: JsonVectorStore) -> None:
    emb = HashingEmbedder()
    first = ingest_file(SAMPLE_DIR / "taskflow.md", store, emb)
    second = ingest_file(SAMPLE_DIR / "taskflow.md", store, emb)
    assert first.chunks == second.chunks == store.count()
    assert store.list_sources() == [{"source": "taskflow.md", "chunks": first.chunks}]


def test_reingest_with_new_content_replaces_old(tmp_path: Path, store: JsonVectorStore) -> None:
    emb = HashingEmbedder()
    doc = tmp_path / "nota.md"
    doc.write_text("# A\nprimera versión\n\n# B\notra sección", encoding="utf-8")
    ingest_file(doc, store, emb)
    doc.write_text("# A\nsegunda versión", encoding="utf-8")
    ingest_file(doc, store, emb)
    assert store.count() == 1
    assert "segunda" in search(store, emb, "versión", top_k=1)[0].chunk.text


def test_dir_skips_invalid_files_without_aborting(tmp_path: Path, store: JsonVectorStore) -> None:
    (tmp_path / "bien.md").write_text("# Hola\ncontenido", encoding="utf-8")
    (tmp_path / "virus.exe").write_bytes(b"MZ")
    (tmp_path / ".oculto.md").write_text("no", encoding="utf-8")
    (tmp_path / "subcarpeta").mkdir()
    report = ingest_dir(tmp_path, store, HashingEmbedder())
    assert [r.source for r in report.ingested] == ["bien.md"]
    assert report.skipped and report.skipped[0][0] == "virus.exe"
    assert "no permitida" in report.skipped[0][1]


def test_empty_document_warns_and_adds_nothing(tmp_path: Path, store: JsonVectorStore) -> None:
    (tmp_path / "vacio.md").write_text("  \n\n", encoding="utf-8")
    report = ingest_file(tmp_path / "vacio.md", store, HashingEmbedder())
    assert report.chunks == 0 and report.warnings and store.count() == 0


def test_index_survives_restart(tmp_path: Path) -> None:
    emb = HashingEmbedder()
    ingest_dir(SAMPLE_DIR, JsonVectorStore(tmp_path / "index"), emb)
    reopened = JsonVectorStore(tmp_path / "index")  # "reinicio del proceso"
    assert reopened.count() > 0
    hits = search(reopened, emb, "reintentos", top_k=3)
    assert any(h.chunk.metadata["section"] == "Reintentos" for h in hits)


def test_search_with_source_filter(tmp_path: Path, store: JsonVectorStore) -> None:
    emb = HashingEmbedder()
    (tmp_path / "otro.md").write_text("# Otro\nreintentos en otro documento", encoding="utf-8")
    ingest_dir(SAMPLE_DIR, store, emb)
    ingest_file(tmp_path / "otro.md", store, emb)
    hits = search(store, emb, "reintentos", top_k=10, source="otro.md")
    assert {h.chunk.source for h in hits} == {"otro.md"}


def test_ingest_logs_sizes_not_content(logs_dir: Path, store: JsonVectorStore) -> None:
    ingest_file(SAMPLE_DIR / "taskflow.md", store, HashingEmbedder())
    raw = next(logs_dir.glob("agent-*.jsonl")).read_text(encoding="utf-8")
    event = json.loads(raw.splitlines()[0])
    assert event["event"] == "ingest" and event["source"] == "taskflow.md" and event["chunks"] > 0
    assert "TaskFlow es una librería" not in raw


def test_cli_ingests_and_searches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, data_dir=tmp_path))
    emb = HashingEmbedder()
    assert main([str(SAMPLE_DIR), "--buscar", "reintentos", "--top-k", "3"], embedder=emb) == 0
    out = capsys.readouterr().out
    assert "indexado taskflow.md" in out and "[Reintentos]" in out and "taskflow.md#" in out
    # segunda ejecución solo buscando: usa el índice guardado en disco
    assert main(["--buscar", "reintentos"], embedder=emb) == 0
    assert "[Reintentos]" in capsys.readouterr().out
    assert (tmp_path / "index" / "index.json").exists()


def test_cli_without_arguments_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], embedder=HashingEmbedder()) == 1
    assert "usage" in capsys.readouterr().out.lower()
