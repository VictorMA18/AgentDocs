"""Tests específicos de ChromaVectorStore (el contrato común está en test_store_contract)."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("chromadb")

from techdoc_agent.rag.embeddings import normalize  # noqa: E402
from techdoc_agent.rag.store import Chunk  # noqa: E402
from techdoc_agent.rag.store_chroma import SOURCE_KEY, ChromaVectorStore  # noqa: E402
from techdoc_agent.rag.store_json import JsonVectorStore  # noqa: E402


def corpus(n: int = 40, dim: int = 16) -> tuple[list[Chunk], np.ndarray]:
    rng = np.random.default_rng(7)
    vectors = np.stack([normalize(rng.normal(size=dim)) for _ in range(n)]).astype(np.float32)
    chunks = [
        Chunk(f"d{i % 3}.md#{i}", f"d{i % 3}.md", f"texto {i}", {"chunk_index": i, "section": f"s{i}"})
        for i in range(n)
    ]
    return chunks, vectors


def test_score_is_one_minus_cosine_distance(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    chunks, vectors = corpus()
    store.add(chunks, vectors)
    raw = store._collection.query(query_embeddings=[vectors[0].tolist()], n_results=3)
    hits = store.search(vectors[0], top_k=3)
    assert [h.score for h in hits] == pytest.approx([1.0 - d for d in raw["distances"][0]])
    assert hits[0].chunk.id == chunks[0].id and hits[0].score == pytest.approx(1.0, abs=1e-4)


def test_source_key_is_internal_only(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    chunks, vectors = corpus(3)
    store.add(chunks, vectors)
    assert SOURCE_KEY in store._collection.get(include=["metadatas"])["metadatas"][0]
    assert all(SOURCE_KEY not in h.chunk.metadata for h in store.search(vectors[0], top_k=3))


def test_matches_json_store_on_same_corpus(tmp_path: Path) -> None:
    chunks, vectors = corpus()
    json_store, chroma = JsonVectorStore(tmp_path / "json"), ChromaVectorStore(tmp_path / "chroma")
    for s in (json_store, chroma):
        s.add(chunks, vectors)
    rng = np.random.default_rng(1)
    for _ in range(10):
        query = normalize(rng.normal(size=16)).astype(np.float32)
        for source in (None, "d1.md"):
            expected = json_store.search(query, top_k=5, source=source)
            got = chroma.search(query, top_k=5, source=source)
            assert [h.chunk for h in got] == [h.chunk for h in expected]
            assert [h.score for h in got] == pytest.approx([h.score for h in expected], abs=1e-4)


def test_add_splits_into_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    monkeypatch.setattr(store._client, "get_max_batch_size", lambda: 7)
    chunks, vectors = corpus(30)
    store.add(chunks, vectors)
    assert store.count() == 30
