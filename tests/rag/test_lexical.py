"""BM25 hecho a mano: tokenización y orden de resultados."""

import pytest

from techdoc_agent.rag.lexical import Bm25Index, fold, tokenize
from techdoc_agent.rag.store import Chunk


def chunk(n: int, text: str) -> Chunk:
    return Chunk(f"d.md#{n}", "d.md", text)


def test_tokenize_folds_case_accents_and_drops_stopwords() -> None:
    assert tokenize("¿Qué es la Configuración?") == ["configuracion"]
    assert fold("ÁÉÍ") == "aei"


def test_compound_terms_are_kept_whole_and_split() -> None:
    assert tokenize("ack_batch_window") == ["ack_batch_window", "ack", "batch", "window"]
    assert tokenize("E-4021") == ["e-4021", "4021"]  # la letra suelta se descarta
    assert tokenize("--drain-timeout") == ["drain-timeout", "drain", "timeout"]


def test_exact_identifier_ranks_first_among_similar_ones() -> None:
    chunks = [chunk(0, "### E-4012 firma inválida"), chunk(1, "### E-4021 cuota excedida"),
              chunk(2, "### E-4030 mensaje duplicado")]
    hits = Bm25Index(chunks).search("error E-4021", top_k=3)
    assert hits[0][0].id == "d.md#1" and hits[0][1] > 0


def test_whole_compound_beats_a_partial_match() -> None:
    chunks = [chunk(0, "ack_batch_size agrupa acuses"), chunk(1, "ack_batch_window espera un lote")]
    assert Bm25Index(chunks).search("ack_batch_window", top_k=2)[0][0].id == "d.md#1"


def test_rarer_terms_weigh_more_and_scores_are_sorted() -> None:
    chunks = [chunk(0, "cola cola cola"), chunk(1, "cola unicornio"), chunk(2, "nada")]
    hits = Bm25Index(chunks).search("cola unicornio", top_k=5)
    assert [c.id for c, _ in hits] == ["d.md#1", "d.md#0"]
    assert hits[0][1] > hits[1][1]


@pytest.mark.parametrize("query", ["", "   ", "¿qué es la?", "zzzz"])
def test_no_terms_or_no_matches_return_nothing(query: str) -> None:
    assert Bm25Index([chunk(0, "texto cualquiera")]).search(query, top_k=3) == []


def test_empty_index_and_top_k_limits() -> None:
    assert Bm25Index([]).search("algo", top_k=3) == []
    index = Bm25Index([chunk(0, "gato"), chunk(1, "gato gato")])
    assert len(index.search("gato", top_k=1)) == 1 and index.search("gato", top_k=0) == []
