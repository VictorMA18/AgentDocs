"""Fusión RRF y modos de ``retrieval.search`` (vector, lexical, hybrid)."""

from pathlib import Path

import numpy as np
import pytest
from fakes import STORE_KINDS, HashingEmbedder, make_store

from techdoc_agent.rag.hybrid import RRF_K, rrf_fuse, with_lexical_floor
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


def test_lexical_floor_brings_in_a_strong_exact_match_that_rrf_buried() -> None:
    fused = ["a", "b", "c", "d", "e", "f"]            # orden de la fusión; "x" quedó fuera del top 3
    lexical = [("y", 40.0), ("x", 38.0), ("a", 3.0)]
    result = with_lexical_floor(fused, lexical, top_k=3, min_score=4.0)
    assert result == ["a", "y", "x"] and len(result) == 3  # lo que ya estaba conserva su orden; entran los 2 léxicos


def test_lexical_floor_respects_threshold_and_does_not_reorder_what_is_there() -> None:
    fused = ["a", "b", "c", "d"]
    assert with_lexical_floor(fused, [("z", 3.9)], top_k=3, min_score=4.0) == ["a", "b", "c"]  # bajo el umbral
    assert with_lexical_floor(fused, [("b", 50.0), ("a", 40.0)], top_k=3, min_score=4.0) == ["a", "b", "c"]  # ya estaban
    assert with_lexical_floor(fused, [], top_k=3, min_score=4.0) == ["a", "b", "c"]
    assert with_lexical_floor(fused, [("z", 9.0), ("w", 8.0), ("v", 7.0), ("u", 6.0)], top_k=4, min_score=1.0) == ["a", "z", "w", "v"]  # solo reserva 3
    assert with_lexical_floor(["a"], [("z", 9.0)], top_k=1, min_score=1.0) == ["z"]


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


def test_lexical_reserve_setting_is_used_and_zero_means_pure_rrf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from techdoc_agent import config

    embedder = HashingEmbedder()
    store = make_store("json", tmp_path / "index")
    chunks = [Chunk(f"d.md#{i}", "d.md", f"tema común número {i} general") for i in range(12)]
    chunks.append(Chunk("d.md#12", "d.md", "el identificador raro ZETAUNICO aparece solo aquí"))
    store.add(chunks, embedder.embed_documents([c.text for c in chunks]))
    base = {"SEARCH_MODE": "hybrid", "LEXICAL_MIN": "0.1"}
    monkeypatch.setattr(config, "settings", config.load_settings({**base, "LEXICAL_RESERVE": "1"}))
    with_floor = [h.chunk.id for h in search(store, embedder, "ZETAUNICO tema común", top_k=1, mode="hybrid")]
    monkeypatch.setattr(config, "settings", config.load_settings({**base, "LEXICAL_RESERVE": "0"}))
    pure_rrf = [h.chunk.id for h in search(store, embedder, "ZETAUNICO tema común", top_k=1, mode="hybrid")]
    assert with_floor == ["d.md#12"] and len(pure_rrf) == 1
