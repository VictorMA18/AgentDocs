"""Tests del almacén JSON + numpy."""

import json
from pathlib import Path

import numpy as np
import pytest

from techdoc_agent.rag.embeddings import normalize
from techdoc_agent.rag.store import Chunk
from techdoc_agent.rag.store_json import JsonVectorStore


def chunk(source: str, n: int, text: str = "") -> Chunk:
    return Chunk(f"{source}#{n}", source, text or f"texto {source} {n}", {"chunk_index": n})


# vectores 3D ya normalizados: ejes x, y, z
X, Y, Z = (np.eye(3, dtype=np.float32)[i] for i in range(3))


@pytest.fixture
def store(tmp_path: Path) -> JsonVectorStore:
    s = JsonVectorStore(tmp_path / "index")
    s.add([chunk("a.md", 0), chunk("a.md", 1), chunk("b.md", 0)], np.stack([X, Y, Z]))
    return s


def test_search_orders_by_cosine_score(store: JsonVectorStore) -> None:
    query = normalize(np.array([0.9, 0.1, 0.0]))
    hits = store.search(query, top_k=3)
    assert [h.chunk.id for h in hits] == ["a.md#0", "a.md#1", "b.md#0"]
    assert hits[0].score == pytest.approx(float(query @ X))
    assert hits[0].score > hits[1].score > hits[2].score
    assert isinstance(hits[0].score, float)


def test_top_k_limits_and_exceeding_is_fine(store: JsonVectorStore) -> None:
    assert len(store.search(X, top_k=1)) == 1
    assert len(store.search(X, top_k=50)) == 3
    assert store.search(X, top_k=0) == []


def test_source_filter(store: JsonVectorStore) -> None:
    hits = store.search(X, top_k=5, source="b.md")
    assert [h.chunk.id for h in hits] == ["b.md#0"]
    assert store.search(X, source="no-existe.md") == []


def test_empty_store(tmp_path: Path) -> None:
    s = JsonVectorStore(tmp_path / "vacio")
    assert s.count() == 0 and s.search(X) == [] and s.list_sources() == []
    assert s.delete_source("x") == 0


def test_count_and_list_sources(store: JsonVectorStore) -> None:
    assert store.count() == 3
    assert store.list_sources() == [{"source": "a.md", "chunks": 2}, {"source": "b.md", "chunks": 1}]


def test_delete_source(store: JsonVectorStore) -> None:
    assert store.delete_source("a.md") == 2
    assert store.count() == 1
    assert [h.chunk.source for h in store.search(X, top_k=5)] == ["b.md"]
    assert store.delete_source("a.md") == 0


def test_same_id_replaces_previous_chunk(store: JsonVectorStore) -> None:
    store.add([chunk("a.md", 0, "texto nuevo")], np.stack([Z]))
    assert store.count() == 3
    best = store.search(Z, top_k=1)[0]
    assert best.score == pytest.approx(1.0)
    assert {h.chunk.text for h in store.search(Z, top_k=3)} >= {"texto nuevo"}


def test_dimension_mismatch_is_rejected(store: JsonVectorStore) -> None:
    with pytest.raises(ValueError, match="Reindexa"):
        store.add([chunk("c.md", 0)], np.ones((1, 5), dtype=np.float32))
    with pytest.raises(ValueError, match="forma"):
        store.search(np.ones(5, dtype=np.float32))


def test_rows_must_match_chunks(store: JsonVectorStore) -> None:
    with pytest.raises(ValueError, match="filas"):
        store.add([chunk("c.md", 0), chunk("c.md", 1)], np.stack([X]))


def test_persistence_across_instances(store: JsonVectorStore, tmp_path: Path) -> None:
    reopened = JsonVectorStore(tmp_path / "index")
    assert reopened.count() == 3
    assert reopened.list_sources() == store.list_sources()
    hit = reopened.search(Y, top_k=1)[0]
    assert hit.chunk.id == "a.md#1" and hit.chunk.metadata == {"chunk_index": 1}


def test_files_on_disk_are_readable(store: JsonVectorStore, tmp_path: Path) -> None:
    index = tmp_path / "index"
    data = json.loads((index / "index.json").read_text(encoding="utf-8"))
    assert data["dimension"] == 3 and len(data["chunks"]) == 3
    assert np.load(index / "vectors.npy").shape == (3, 3)
    assert not list(index.glob("*.tmp"))  # sin temporales tras guardar


def test_persists_deletions(store: JsonVectorStore, tmp_path: Path) -> None:
    store.delete_source("a.md")
    assert JsonVectorStore(tmp_path / "index").count() == 1


def test_corrupt_index_is_detected(store: JsonVectorStore, tmp_path: Path) -> None:
    np.save(tmp_path / "index" / "vectors.npy", np.zeros((1, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="corrupto"):
        JsonVectorStore(tmp_path / "index")
