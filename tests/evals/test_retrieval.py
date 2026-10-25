"""Evaluación de la recuperación sin LLM (con el embedder de pruebas, sin descargar modelos)."""

from pathlib import Path

from fakes import HashingEmbedder

from evals import retrieval
from evals.dataset import Case
from techdoc_agent.rag.store import Chunk, SearchHit


def hit(text: str, source: str = "e.md", score: float = 0.9, lexical: float | None = None) -> SearchHit:
    return SearchHit(Chunk(f"{source}#0", source, text), score, lexical)


def test_evidence_is_matched_at_chunk_level_ignoring_case_and_accents() -> None:
    case = Case(id="c", question="p", expect_sources=("e.md",), expect_evidence=("quota_messages",))
    assert retrieval.evaluate_mode(case, [hit("otro"), hit("Su `QUOTA_MESSAGES` es")]).reciprocal_rank == 0.5
    assert retrieval.evaluate_mode(case, [hit("otro fragmento")]).hit is False


def test_without_evidence_the_expected_source_decides() -> None:
    case = Case(id="c", question="p", expect_sources=("e.md",))
    assert retrieval.evaluate_mode(case, [hit("x", "z.md"), hit("y", "e.md")]).reciprocal_rank == 0.5


def test_admitted_applies_the_same_filter_as_the_tool() -> None:
    case = Case(id="c", question="p", expect_evidence=("clave",))
    weak = [hit("clave", score=0.01)]
    assert retrieval.evaluate_mode(case, weak) .hit and not retrieval.evaluate_mode(case, weak).admitted_hit
    strong_word = [hit("clave", score=0.01, lexical=99.0)]
    assert retrieval.evaluate_mode(case, strong_word).admitted_hit


def test_main_prints_a_report_for_the_real_dataset_subset(capsys, tmp_path: Path) -> None:
    code = retrieval.main(["--only", "dificil-error-e4021,fuera-alcance-k8s", "--top-k", "3"],
                          embedder=HashingEmbedder())
    out = capsys.readouterr().out
    assert code == 0 and "dificil-error-e4021" in out and "exact_term" in out
    assert "fuera de alcance" in out and "vector" in out and "hybrid" in out


def test_main_rejects_unknown_ids_and_invalid_top_k(capsys) -> None:
    assert retrieval.main(["--only", "no-existe"], embedder=HashingEmbedder()) == 2
    assert retrieval.main(["--top-k", "0"], embedder=HashingEmbedder()) == 2
