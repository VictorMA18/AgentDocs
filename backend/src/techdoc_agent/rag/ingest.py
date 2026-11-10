"""Ingesta: archivo → texto → fragmentos → embeddings → almacén.

Uso desde consola (ver ``main``)::

    python -m techdoc_agent.rag.ingest data/sample_docs --buscar "reintentos"
    python -m techdoc_agent.rag.ingest --buscar "reintentos"      # solo buscar
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from techdoc_agent import config
from techdoc_agent.logging_setup import log_event
from techdoc_agent.rag.chunking import chunk_document
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.loaders import load_file
from techdoc_agent.rag.retrieval import search
from techdoc_agent.rag.store import VectorStore
from techdoc_agent.rag.factory import build_store


@dataclass
class IngestReport:
    source: str
    chunks: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class DirReport:
    ingested: list[IngestReport] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (archivo, motivo)


def ingest_file(path: str | Path, store: VectorStore, embedder: Embedder) -> IngestReport:
    """Indexa un archivo. Reingestar el mismo nombre reemplaza sus fragmentos."""
    started = perf_counter()
    doc = load_file(path)
    chunks = chunk_document(doc)
    warnings = list(doc.warnings)

    store.delete_source(doc.source)  # idempotente: no se duplican fragmentos
    if chunks:
        store.add(chunks, embedder.embed_documents([c.text for c in chunks]))
    else:
        warnings.append("El documento no tiene contenido indexable")

    log_event(event="ingest", source=doc.source, chunks=len(chunks), chars=len(doc.text),
              warnings=len(warnings), duration_ms=round((perf_counter() - started) * 1000))
    return IngestReport(doc.source, len(chunks), warnings)


def ingest_dir(directory: str | Path, store: VectorStore, embedder: Embedder) -> DirReport:
    """Indexa los archivos de una carpeta; los inválidos se omiten y se reportan."""
    report = DirReport()
    for path in sorted(Path(directory).iterdir()):
        if path.name.startswith(".") or not path.is_file():
            continue
        try:
            report.ingested.append(ingest_file(path, store, embedder))
        except ValueError as exc:
            report.skipped.append((path.name, str(exc)))
    return report


# --- script de consola ---


def _print_ingest(path: Path, store: VectorStore, embedder: Embedder) -> None:
    if path.is_dir():
        report = ingest_dir(path, store, embedder)
        reports, skipped = report.ingested, report.skipped
    else:
        reports, skipped = [ingest_file(path, store, embedder)], []
    for r in reports:
        print(f"  indexado {r.source}: {r.chunks} fragmentos")
        for warning in r.warnings:
            print(f"    ⚠ {warning}")
    for name, reason in skipped:
        print(f"  omitido {name}: {reason}")
    print(f"Índice: {store.count()} fragmentos en {len(store.list_sources())} documento(s)\n")


def _print_hits(query: str, store: VectorStore, embedder: Embedder, top_k: int, source: str | None) -> None:
    hits = search(store, embedder, query, top_k=top_k, source=source)
    print(f'Top {top_k} para "{query}":')
    if not hits:
        print("  (sin resultados)")
    for rank, hit in enumerate(hits, start=1):
        body = hit.chunk.text.replace("\n", " ")
        print(f"  {rank}. {hit.score:.3f}  {hit.chunk.id:<16} [{hit.chunk.metadata.get('section', '')}]  {body[:90]}")


def main(argv: list[str] | None = None, *, embedder: Embedder | None = None) -> int:
    parser = argparse.ArgumentParser(description="Indexa documentos y busca en el índice local.")
    parser.add_argument("ruta", nargs="?", help="archivo o carpeta a indexar")
    parser.add_argument("--buscar", metavar="CONSULTA", help="busca esta consulta tras indexar")
    parser.add_argument("--top-k", type=int, default=config.settings.top_k_default)
    parser.add_argument("--fuente", help="limita la búsqueda a un documento")
    args = parser.parse_args(argv)
    if not args.ruta and not args.buscar:
        parser.print_help()
        return 1

    if embedder is None:
        from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder

        print(f"Cargando modelo {config.settings.embedding_model} (la primera vez se descarga)...")
        embedder = SentenceTransformerEmbedder()
    store = build_store()

    if args.ruta:
        _print_ingest(Path(args.ruta), store, embedder)
    if args.buscar:
        _print_hits(args.buscar, store, embedder, args.top_k, args.fuente)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
