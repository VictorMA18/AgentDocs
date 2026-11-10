"""Fusión de rankings por *Reciprocal Rank Fusion* (RRF).

Las puntuaciones de la búsqueda vectorial (coseno, 0-1) y de BM25 (sin tope) no se pueden sumar.
RRF solo usa la **posición** de cada fragmento en cada ranking: ``1 / (K + posición)``. Un fragmento
que sale alto en cualquiera de los dos rankings, o medio en ambos, sube.
"""

from __future__ import annotations

RRF_K = 60  # valor habitual: suaviza la diferencia entre las primeras posiciones
DEFAULT_LEXICAL_RESERVE = 3  # mejores resultados léxicos que no pueden quedar fuera del top-k (``LEXICAL_RESERVE``)


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Une rankings de ids (el mejor primero). Devuelve ``(id, puntuación)`` de mayor a menor;
    a igualdad gana el que apareció antes (primero en el primer ranking)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, id_ in enumerate(ranking, start=1):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: -item[1])  # sorted es estable


def with_lexical_floor(
    fused_ids: list[str], lexical: list[tuple[str, float]], top_k: int, min_score: float, reserve: int = DEFAULT_LEXICAL_RESERVE
) -> list[str]:
    """Los ``top_k`` primeros de la fusión, asegurando que los mejores resultados léxicos entren.

    RRF mira posiciones, no puntuaciones: un fragmento que solo gana por una coincidencia exacta fuerte
    (BM25 alto, pero ausente de los primeros de la vectorial) queda por debajo de otros mediocres que
    aparecen en ambas listas. Medido con un PDF real: ``HTTPAdapter(pool_connections: int = 10, ...)``
    era el 2.º por BM25 (38,8) y quedaba fuera del top 5 de la híbrida; con 2 reservas, la firma de ``pool_block`` (3.ª por BM25) seguía fuera. Aquí, los ``reserve`` mejores
    léxicos con BM25 >= ``min_score`` que no estén ya en el top-k sustituyen a las últimas posiciones;
    el orden de lo que ya estaba no cambia.
    """
    head = fused_ids[:top_k]
    wanted = [id_ for id_, score in lexical[:reserve] if score >= min_score]
    missing = [id_ for id_ in wanted if id_ not in head]
    if not missing:
        return head
    return head[: max(top_k - len(missing), 0)] + missing[:top_k]
