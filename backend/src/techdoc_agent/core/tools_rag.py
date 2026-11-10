"""Herramientas del agente sobre el RAG: ``buscar_documentos`` y ``listar_documentos``.

El agente decide cuándo llamarlas; aquí solo se validan los argumentos, se aplica
el umbral ``MIN_SCORE`` y se formatea el resultado. Cada fragmento se entrega
dentro de ``<documento>`` y su contenido es un dato no confiable (docs/04 §6).
"""

from __future__ import annotations

from techdoc_agent import config
from techdoc_agent.core.tools import Tool
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.retrieval import search
from techdoc_agent.rag.store import SearchHit, VectorStore

NO_RESULTS = "Sin resultados relevantes para esa consulta."
NO_DOCUMENTS = "No hay documentos indexados."
MAX_TOP_K = 10


def _attr(value: object) -> str:
    """Valor seguro para un atributo entre comillas dobles."""
    return str(value).replace('"', "'").replace("\n", " ")


def _neutralize(text: str) -> str:
    """Impide que un documento cierre la etiqueta ``<documento>`` y escape de ella."""
    return text.replace("</documento", "<\\/documento")


def format_hit(hit: SearchHit) -> str:
    chunk = hit.chunk
    return (
        f'<documento fuente="{_attr(chunk.id)}" seccion="{_attr(chunk.metadata.get("section", ""))}" '
        f'score="{hit.score:.2f}">\n{_neutralize(chunk.text)}\n</documento>'
    )


def _is_relevant(hit: SearchHit) -> bool:
    """Pasa el umbral de coseno, o (búsqueda léxica/híbrida) una coincidencia de palabras muy fuerte."""
    if hit.score >= config.settings.min_score:
        return True
    return hit.lexical_score is not None and hit.lexical_score >= config.settings.lexical_min


def rag_tools(store: VectorStore, embedder: Embedder) -> list[Tool]:
    """Crea las herramientas RAG sobre un almacén y un embedder concretos."""

    def buscar_documentos(query: str, top_k: int | None = None, source: str | None = None) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query debe ser un texto no vacío")
        k = config.settings.top_k_default if top_k is None else top_k
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= MAX_TOP_K:
            raise ValueError(f"top_k debe ser un entero entre 1 y {MAX_TOP_K}")
        if source is not None and not isinstance(source, str):
            raise ValueError("source debe ser un nombre de archivo")
        hits = search(store, embedder, query.strip(), top_k=k, source=source or None)
        relevant = [h for h in hits if _is_relevant(h)]
        return "\n\n".join(format_hit(h) for h in relevant) if relevant else NO_RESULTS

    def listar_documentos() -> str:
        sources = store.list_sources()
        if not sources:
            return NO_DOCUMENTS
        return "\n".join(f"- {s['source']}: {s['chunks']} fragmentos" for s in sources)

    return [
        Tool(
            name="buscar_documentos",
            description=(
                "Busca fragmentos relevantes en la documentación indexada del usuario. Úsala "
                "siempre que la pregunta dependa del contenido de los documentos (API, "
                "configuración, ejemplos, requisitos previos). No la uses para saludos ni "
                "preguntas generales. Si el primer resultado es insuficiente, reformula la "
                "consulta con otros términos y vuelve a buscar. Devuelve fragmentos con su "
                "fuente y puntaje de similitud."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta en lenguaje natural, específica y autocontenida.",
                    },
                    "top_k": {"type": "integer", "minimum": 1, "maximum": MAX_TOP_K, "default": 5},
                    "source": {
                        "type": "string",
                        "description": "Opcional: limitar a un documento por nombre de archivo.",
                    },
                },
                "required": ["query"],
            },
            func=buscar_documentos,
        ),
        Tool(
            name="listar_documentos",
            description=(
                "Lista los documentos indexados con su número de fragmentos. Úsala para saber "
                "qué documentación hay disponible antes de buscar, o para responder "
                "'¿qué documentos tengo?'."
            ),
            input_schema={"type": "object", "properties": {}},
            func=listar_documentos,
        ),
    ]
