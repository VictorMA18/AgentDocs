"""Fusión RRF y modos de ``retrieval.search`` (vector, lexical, hybrid)."""

from pathlib import Path

import numpy as np
import pytest
from fakes import STORE_KINDS, HashingEmbedder, make_store

from techdoc_agent.rag.hybrid import RRF_K, rrf_fuse
from techdoc_agent.rag.retrieval import search
from techdoc_agent.rag.store import Chunk


def test_rrf_rewards_appearing_in_both_rankings() -> None:
    fused = rrf_fuse([["a", "b", "c"], ["c", "b", "d"]])
    # b (2.º y 2.º) y c (3.º y 1.º) salen en los dos rankings: superan a a y d, que salen en uno solo
    assert [id_ for id_, _ in fused] == ["c", "b", "a", "d"]
    assert dict(fused)["b"] == pytest.approx(2 / (RRF_K + 2))


def test_rrf_is_deterministic_and_ties_keep_first_appearance() -> None:
    assert rrf_fuse([["a"], ["b"]]) == rrf_fuse([["a"], ["b"]])
    assert [i for i, _ in rrf_fuse([["a"], ["b"]])] == ["a", "b"]
    assert rrf_fuse([]) == [] and rrf_fuse([[], []]) == []


@pytest.fixture(params=STORE_KINDS)
def store(request: pytest.FixtureRequest, tmp_path: Path):
    embedder = HashingEmbedder()
    texts = {"e.md#0": "### E-4012 firma del mensaje inválida", "e.md#1": "### E-4021 cuota de la cola excedida",
             "e.md#2": "### E-4030 mensaje duplicado en la ventana", "g.md#0": "guía general de colas y consumidores"}
    s = make_store(request.param, tmp_path / "index")
    chunks = [Chunk(i, i.split("#")[0], t, {"chunk_index": int(i[-1])}) for i, t in texts.items()]
    s.add(chunks, embedder.embed_documents([c.text for c in chunks]))
    return s


def test_all_chunks_returns_everything_or_one_source(store) -> None:
    assert {c.id for c in store.all_chunks()} == {"e.md#0", "e.md#1", "e.md#2", "g.md#0"}
    assert {c.id for c in store.all_chunks("e.md")} == {"e.md#0", "e.md#1", "e.md#2"}
    assert store.all_chunks("no.md") == []
    one = next(c for c in store.all_chunks() if c.id == "e.md#1")
    assert one.source == "e.md" and "E-4021" in one.text and one.metadata == {"chunk_index": 1}


@pytest.mark.parametrize("mode", ["vector", "lexical", "hybrid"])
def test_every_mode_returns_hits_with_cosine_score(store, mode: str) -> None:
    hits = search(store, HashingEmbedder(), "error E-4021 cuota", top_k=3, mode=mode)
    assert hits and hits[0].chunk.id == "e.md#1"
    assert all(isinstance(h.score, float) for h in hits)
    assert (hits[0].lexical_score is None) == (mode == "vector")


def test_hybrid_and_lexical_expose_bm25_but_vector_does_not(store) -> None:
    query = "E-4021"
    assert search(store, HashingEmbedder(), query, mode="vector")[0].lexical_score is None
    assert search(store, HashingEmbedder(), query, mode="hybrid")[0].lexical_score > 0


def test_lexical_mode_only_returns_chunks_that_match_words(store) -> None:
    hits = search(store, HashingEmbedder(), "duplicado", top_k=5, mode="lexical")
    assert [h.chunk.id for h in hits] == ["e.md#2"]


def test_source_filter_applies_to_every_mode(store) -> None:
    for mode in ("vector", "lexical", "hybrid"):
        hits = search(store, HashingEmbedder(), "guía de colas", top_k=5, source="g.md", mode=mode)
        assert {h.chunk.source for h in hits} <= {"g.md"}


def test_unknown_mode_is_rejected(store) -> None:
    with pytest.raises(ValueError, match="modo de búsqueda desconocido"):
        search(store, HashingEmbedder(), "x", mode="difuso")


def test_empty_store_returns_nothing_in_every_mode(tmp_path: Path) -> None:
    empty = make_store("json", tmp_path / "vacio")
    for mode in ("vector", "lexical", "hybrid"):
        assert search(empty, HashingEmbedder(), "algo", mode=mode) == []
