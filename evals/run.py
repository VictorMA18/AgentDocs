"""Runner de evaluaciones: ``python -m evals.run`` (ver docs/07).

Para cada caso del dataset (y cada repetición) crea un entorno **aislado** (índice, memoria y
carpeta de salidas propios), ejecuta el agente real, juzga el resultado con ``evals.rules`` y
resume por caso y por métrica. Guarda el detalle en ``evals/results/`` (ignorado por git).

Código de salida: 0 si la tasa global ≥ ``EVAL_MIN_PASS``, 1 si no, 2 si el dataset no es válido.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from evals import rules
from evals.dataset import DEFAULT_DATASET, REPO_ROOT, Case, DatasetError, load
from techdoc_agent import config
from techdoc_agent.bootstrap import build_agent
from techdoc_agent.core.llm import LLMClient, LLMError
from techdoc_agent.outputs.artifacts import turn_artifacts
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.ingest import ingest_dir, ingest_file
from techdoc_agent.rag.store import VectorStore
from techdoc_agent.rag.store_json import JsonVectorStore

BASE_DOCS = REPO_ROOT / "data" / "sample_docs"
RESULTS_DIR = REPO_ROOT / "evals" / "results"
PASS_RATE = 0.5  # un caso cuenta como acierto si pasa en al menos la mitad de sus repeticiones

LlmFactory = Callable[[Case, int], LLMClient]


@dataclass
class RunRecord:
    """Una ejecución (una repetición) de un caso."""

    case_id: str
    repetition: int
    checks: dict[str, bool | None]
    passed: bool
    replies: list[str]
    tool_calls: list[dict[str, Any]]
    retrieved_sources: list[str]
    searches: int
    artifacts: list[dict[str, str]]
    input_tokens: int
    output_tokens: int
    duration_ms: int
    error: str | None = None


@dataclass
class CaseResult:
    case: Case
    runs: list[RunRecord] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return sum(r.passed for r in self.runs) / len(self.runs)

    @property
    def passed(self) -> bool:
        return self.pass_rate >= PASS_RATE


class _LockedEmbedder:
    """Serializa el embedder compartido: varios casos a la vez no deben usar el modelo a la vez."""

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self._lock = threading.Lock()

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> np.ndarray:
        with self._lock:
            return self._inner.embed_query(text)


# --- ejecución de un caso ---


def _ask(agent: Any, session: str, message: str) -> Any:
    """Un turno; si el LLM falla se reintenta una vez (``Agent.run`` ya deshace el turno fallido)."""
    try:
        return agent.run(session, message)
    except LLMError:
        return agent.run(session, message)


def _open_store(folder: Path) -> VectorStore:
    """Índice nuevo del caso, del tipo que diga ``VECTOR_STORE`` (así se puede medir JSON frente a Chroma)."""
    if config.settings.vector_store == "chroma":
        from techdoc_agent.rag.store_chroma import ChromaVectorStore

        return ChromaVectorStore(folder / "chroma")
    return JsonVectorStore(folder / "index")


def run_case(case: Case, repetition: int, *, llm: LLMClient, embedder: Embedder, workdir: Path) -> RunRecord:
    """Ejecuta un caso en un entorno nuevo y lo juzga."""
    folder = workdir / f"{case.id}-r{repetition}"
    outputs = folder / "outputs"
    store = _open_store(folder)
    ingest_dir(BASE_DOCS, store, embedder)
    for doc in case.setup_docs:
        ingest_file(REPO_ROOT / doc, store, embedder)

    agent = build_agent(llm, store, embedder, outputs_dir=outputs)
    session = f"eval-{case.id}-r{repetition}"
    outcome = rules.Outcome()
    input_tokens = output_tokens = 0
    started = perf_counter()
    try:
        for message in (case.question, *case.follow_up):
            result = _ask(agent, session, message)
            outcome.replies.append(result.text)
            outcome.tool_calls.extend(result.tool_calls)
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
    except LLMError as exc:
        outcome.error = str(exc)
    duration_ms = round((perf_counter() - started) * 1000)
    outcome.artifacts = turn_artifacts(outcome.tool_calls, outputs)

    checks = rules.evaluate(case, outcome)
    return RunRecord(
        case_id=case.id, repetition=repetition, checks=checks, passed=rules.passed(checks),
        replies=outcome.replies,
        tool_calls=[{"tool": t.name, "args": t.args, "is_error": t.is_error, "duration_ms": t.duration_ms,
                     "result_chars": len(t.result)} for t in outcome.tool_calls],
        retrieved_sources=sorted(rules.retrieved_sources(outcome)), searches=rules.searches(outcome),
        artifacts=outcome.artifacts, input_tokens=input_tokens, output_tokens=output_tokens,
        duration_ms=duration_ms, error=outcome.error,
    )


@contextmanager
def _logs_in(directory: Path) -> Iterator[None]:
    """Los registros del agente de esta ejecución van a la carpeta del run y luego se restaura."""
    original = config.settings
    config.settings = dataclasses.replace(original, logs_dir=directory)
    try:
        yield
    finally:
        config.settings = original


def run_eval(
    cases: list[Case], *, llm_factory: LlmFactory, embedder: Embedder, workdir: Path, logs_dir: Path,
    repeat: int = 1, workers: int = 1, progress: Callable[[str], None] | None = None,
) -> list[CaseResult]:
    """Ejecuta todos los casos (``repeat`` veces cada uno, ``workers`` a la vez) y los agrupa por caso."""
    shared = _LockedEmbedder(embedder)
    jobs = [(case, rep) for case in cases for rep in range(1, repeat + 1)]
    done = 0
    lock = threading.Lock()

    def work(job: tuple[Case, int]) -> RunRecord:
        nonlocal done
        case, rep = job
        record = run_case(case, rep, llm=llm_factory(case, rep), embedder=shared, workdir=workdir)
        with lock:
            done += 1
            if progress:
                mark = "✓" if record.passed else "✗"
                progress(f"[{done}/{len(jobs)}] {mark} {case.id} (r{rep}) {record.duration_ms / 1000:.1f} s")
        return record

    with _logs_in(logs_dir), ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        records = list(pool.map(work, jobs))  # conserva el orden de los casos

    results = {case.id: CaseResult(case) for case in cases}
    for record in records:
        results[record.case_id].runs.append(record)
    return list(results.values())


# --- resumen y reporte ---


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    """Porcentajes globales y por regla, y consumo medio."""
    runs = [run for result in results for run in result.runs]
    per_check: dict[str, dict[str, float | int]] = {}
    for name in rules.CHECKS:
        applicable = [run.checks[name] for run in runs if run.checks.get(name) is not None]
        if applicable:
            per_check[name] = {"applicable": len(applicable), "rate": sum(applicable) / len(applicable)}
    return {
        "cases": len(results),
        "cases_passed": sum(r.passed for r in results),
        "pass_rate": sum(r.passed for r in results) / len(results),
        "mean_case_rate": sum(r.pass_rate for r in results) / len(results),
        "checks": per_check,
        "mean_tokens": round(sum(r.input_tokens + r.output_tokens for r in runs) / len(runs)),
        "mean_seconds": round(sum(r.duration_ms for r in runs) / len(runs) / 1000, 1),
        "errors": sum(1 for r in runs if r.error),
    }


def format_report(results: list[CaseResult], summary: dict[str, Any], min_pass: float) -> str:
    width = max(len(r.case.id) for r in results)
    lines = [f"{'caso':<{width}}  resultado  reglas fallidas                    tokens   seg"]
    for result in results:
        failed = [name for name in rules.CHECKS if any(run.checks.get(name) is False for run in result.runs)]
        mark = "✓" if result.passed else "✗"
        rate = f"{mark} {result.pass_rate:>4.0%}"
        tokens = round(sum(r.input_tokens + r.output_tokens for r in result.runs) / len(result.runs))
        seconds = sum(r.duration_ms for r in result.runs) / len(result.runs) / 1000
        lines.append(f"{result.case.id:<{width}}  {rate:<9}  {', '.join(failed) or '-':<32}  {tokens:>6}  {seconds:>4.0f}")
    lines += ["", "Por regla (casos a los que aplica):"]
    for name, data in summary["checks"].items():
        lines.append(f"  {name:<14} {data['rate']:>5.0%}  ({data['applicable']})")
    verdict = "SUPERA" if summary["pass_rate"] >= min_pass else "NO SUPERA"
    lines += [
        "",
        f"Global: {summary['cases_passed']}/{summary['cases']} casos = {summary['pass_rate']:.0%} "
        f"(umbral {min_pass:.0%}: {verdict}) · tasa media por caso {summary['mean_case_rate']:.0%}",
        f"Consumo medio por ejecución: {summary['mean_tokens']} tokens, {summary['mean_seconds']} s"
        + (f" · {summary['errors']} ejecuciones con error" if summary["errors"] else ""),
    ]
    return "\n".join(lines)


def save_results(results: list[CaseResult], summary: dict[str, Any], meta: dict[str, Any], path: Path) -> None:
    payload = {
        "meta": meta, "summary": summary,
        "cases": [{"id": r.case.id, "passed": r.passed, "pass_rate": r.pass_rate, "case": asdict(r.case),
                   "runs": [asdict(run) for run in r.runs]} for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


# --- línea de comandos ---


def main(
    argv: list[str] | None = None, *, llm_factory: LlmFactory | None = None, embedder: Embedder | None = None,
    results_dir: Path = RESULTS_DIR, workdir: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Evalúa el agente con el dataset de evals/.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--only", help="ids de casos separados por comas")
    parser.add_argument("--repeat", type=int, default=1, help="repeticiones por caso (el modelo no es determinista)")
    parser.add_argument("--workers", type=int, default=4, help="casos en paralelo (1 = en serie; los tiempos son más fiables)")
    parser.add_argument("--min-pass", type=float, default=config.settings.eval_min_pass)
    parser.add_argument("--label", default="", help="etiqueta de la ejecución (p. ej. linea-base)")
    args = parser.parse_args(argv)

    try:
        cases = load(args.dataset)
        if args.only:
            wanted = [i.strip() for i in args.only.split(",") if i.strip()]
            unknown = sorted(set(wanted) - {c.id for c in cases})
            if unknown:
                raise DatasetError(f"--only: ids desconocidos: {', '.join(unknown)}")
            cases = [c for c in cases if c.id in wanted]
    except DatasetError as exc:
        print(f"Dataset no válido: {exc}", file=sys.stderr)
        return 2
    if args.repeat < 1 or args.workers < 1:
        print("--repeat y --workers deben ser al menos 1", file=sys.stderr)
        return 2

    if embedder is None:
        from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder

        print(f"Cargando modelo {config.settings.embedding_model}…", file=sys.stderr)
        embedder = SentenceTransformerEmbedder()
    if llm_factory is None:
        from techdoc_agent.core.llm import ClaudeCliClient

        client = ClaudeCliClient()
        llm_factory = lambda case, rep: client  # noqa: E731 - el cliente no guarda estado entre llamadas

    started = datetime.now()
    run_name = started.strftime("%Y%m%d-%H%M%S") + (f"-{args.label}" if args.label else "")
    import tempfile

    with tempfile.TemporaryDirectory(prefix="evals-") as tmp:
        print(f"{len(cases)} casos × {args.repeat} repetición(es), {args.workers} en paralelo", file=sys.stderr)
        results = run_eval(
            cases, llm_factory=llm_factory, embedder=embedder, workdir=workdir or Path(tmp),
            logs_dir=results_dir / run_name / "logs", repeat=args.repeat, workers=args.workers,
            progress=lambda line: print(line, file=sys.stderr),
        )
    summary = summarize(results)
    meta = {"started": started.isoformat(timespec="seconds"), "label": args.label, "model": config.settings.model,
            "vector_store": config.settings.vector_store, "min_score": config.settings.min_score,
            "chunk_size": config.settings.chunk_size, "top_k_default": config.settings.top_k_default,
            "repeat": args.repeat, "workers": args.workers, "dataset": args.dataset.name, "min_pass": args.min_pass}
    save_results(results, summary, meta, results_dir / f"{run_name}.json")

    print(format_report(results, summary, args.min_pass))
    print(f"\nDetalle: {results_dir / (run_name + '.json')}")
    return 0 if summary["pass_rate"] >= args.min_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
