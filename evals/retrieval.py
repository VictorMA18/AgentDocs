"""Evaluación de la recuperación **sin LLM** (Fase 7.B): compara ``vector``, ``lexical`` e ``hybrid``.

Para cada caso con ``expect_evidence`` o ``expect_sources`` indexa los documentos del caso (como el
runner) y mira qué fragmentos devuelve la consulta literal del caso. Tarda segundos y no gasta tokens,
así que sirve para ajustar parámetros antes de pasar por el modelo.

- **hit@k**: los fragmentos devueltos contienen la evidencia esperada (o, si el caso no la define, las
  fuentes esperadas).
- **MRR**: 1 / posición del primer fragmento que la contiene (0 si no aparece).
- **admitidos**: lo mismo, pero después del filtro que aplica ``buscar_documentos`` (``MIN_SCORE`` y
  ``LEXICAL_MIN``), que es lo que de verdad ve el agente.
- **falsos admitidos** (casos ``out_of_scope``): fragmentos que el filtro deja pasar cuando debería no haber
  nada relevante. Informativo: la búsqueda vectorial también admite algunos.

Uso: ``python -m evals.retrieval [--top-k 5] [--only id1,id2] [--dataset ruta]``
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from evals.dataset import DEFAULT_DATASET, REPO_ROOT, Case, DatasetError, load
from evals.rules import fold
from evals.run import BASE_DOCS, _open_store
from techdoc_agent import config
from techdoc_agent.core.tools_rag import _is_relevant
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.ingest import ingest_dir, ingest_file
from techdoc_agent.rag.retrieval import SEARCH_MODES, search
from techdoc_agent.rag.store import SearchHit


@dataclass
class ModeResult:
    hit: bool
    reciprocal_rank: float
    admitted_hit: bool
    admitted_count: int


def _matches(case: Case, hit: SearchHit) -> bool:
    """¿Este fragmento es la evidencia del caso? Con evidencia: contiene todos los textos; si no, es de la fuente."""
    if case.expect_evidence:
        text = fold(hit.chunk.text)
        return all(fold(token) in text for token in case.expect_evidence)
    return hit.chunk.source in case.expect_sources


def evaluate_mode(case: Case, hits: list[SearchHit]) -> ModeResult:
    rank = next((i for i, h in enumerate(hits, start=1) if _matches(case, h)), None)
    admitted = [h for h in hits if _is_relevant(h)]
    return ModeResult(
        hit=rank is not None,
        reciprocal_rank=1 / rank if rank else 0.0,
        admitted_hit=any(_matches(case, h) for h in admitted),
        admitted_count=len(admitted),
    )


def evaluate_case(case: Case, embedder: Embedder, top_k: int, folder: Path) -> dict[str, ModeResult]:
    store = _open_store(folder)
    ingest_dir(BASE_DOCS, store, embedder)
    for doc in case.setup_docs:
        ingest_file(REPO_ROOT / doc, store, embedder)
    return {mode: evaluate_mode(case, search(store, embedder, case.question, top_k=top_k, mode=mode))
            for mode in SEARCH_MODES}


def run(cases: list[Case], embedder: Embedder, top_k: int, workdir: Path) -> dict[str, dict[str, ModeResult]]:
    """Resultados por caso (solo los que tienen algo que recuperar o son fuera de alcance)."""
    results = {}
    for case in cases:
        if case.expect_evidence or case.expect_sources or case.out_of_scope:
            results[case.id] = evaluate_case(case, embedder, top_k, workdir / case.id)
    return results


def format_report(cases: list[Case], results: dict[str, dict[str, ModeResult]], top_k: int) -> str:
    by_id = {c.id: c for c in cases}
    lines = [f"Recuperación con top_k={top_k}, MIN_SCORE={config.settings.min_score}, "
             f"LEXICAL_MIN={config.settings.lexical_min}", "",
             f"{'caso':<36} {'tipo':<11} " + " ".join(f"{m:^15}" for m in SEARCH_MODES),
             f"{'':<36} {'':<11} " + " ".join(f"{'hit  RR  adm':^15}" for _ in SEARCH_MODES)]
    groups: dict[str, list[str]] = defaultdict(list)
    false_admitted = dict.fromkeys(SEARCH_MODES, 0)
    scored: list[str] = []
    for id_, per_mode in results.items():
        case = by_id[id_]
        if case.out_of_scope:
            for mode in SEARCH_MODES:
                false_admitted[mode] += per_mode[mode].admitted_count
            continue
        scored.append(id_)
        groups[case.kind or "general"].append(id_)
        cells = " ".join(
            f"{'sí' if r.hit else 'NO':^4} {r.reciprocal_rank:>4.2f} {'sí' if r.admitted_hit else 'NO':^4}  "
            for r in (per_mode[m] for m in SEARCH_MODES))
        lines.append(f"{id_:<36} {case.kind or '-':<11} {cells}")
    lines += ["", "Resumen por tipo (hit@k · MRR · admitidos):"]
    for name, ids in sorted(groups.items()):
        row = []
        for mode in SEARCH_MODES:
            rs = [results[i][mode] for i in ids]
            row.append(f"{mode} {sum(r.hit for r in rs)}/{len(rs)} · {sum(r.reciprocal_rank for r in rs) / len(rs):.2f}"
                       f" · {sum(r.admitted_hit for r in rs)}/{len(rs)}")
        lines.append(f"  {name:<11} " + "   ".join(row))
    allr = {m: [results[i][m] for i in scored] for m in SEARCH_MODES}
    lines.append(f"  {'TODOS':<11} " + "   ".join(
        f"{m} {sum(r.hit for r in rs)}/{len(rs)} · {sum(r.reciprocal_rank for r in rs) / len(rs):.2f}"
        f" · {sum(r.admitted_hit for r in rs)}/{len(rs)}" for m, rs in allr.items()))
    out = [i for i in results if by_id[i].out_of_scope]
    lines += ["", f"Fragmentos admitidos en {len(out)} casos fuera de alcance (menos es mejor): "
              + ", ".join(f"{m} {n}" for m, n in false_admitted.items())]
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, embedder: Embedder | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compara vector, lexical e hybrid sin usar el modelo.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--only", help="ids de casos separados por comas")
    parser.add_argument("--top-k", type=int, default=config.settings.top_k_default)
    args = parser.parse_args(argv)
    try:
        cases = load(args.dataset)
        if args.only:
            wanted = {i.strip() for i in args.only.split(",") if i.strip()}
            unknown = sorted(wanted - {c.id for c in cases})
            if unknown:
                raise DatasetError(f"--only: ids desconocidos: {', '.join(unknown)}")
            cases = [c for c in cases if c.id in wanted]
    except DatasetError as exc:
        print(f"Dataset no válido: {exc}", file=sys.stderr)
        return 2
    if args.top_k < 1:
        print("--top-k debe ser al menos 1", file=sys.stderr)
        return 2
    if embedder is None:
        from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder

        print(f"Cargando modelo {config.settings.embedding_model}…", file=sys.stderr)
        embedder = SentenceTransformerEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        results = run(cases, embedder, args.top_k, Path(tmp))
    print(format_report(cases, results, args.top_k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
