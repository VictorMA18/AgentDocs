"""Fusión de rankings por *Reciprocal Rank Fusion* (RRF).

Las puntuaciones de la búsqueda vectorial (coseno, 0-1) y de BM25 (sin tope) no se pueden sumar.
RRF solo usa la **posición** de cada fragmento en cada ranking: ``1 / (K + posición)``. Un fragmento
que sale alto en cualquiera de los dos rankings, o medio en ambos, sube.
"""

from __future__ import annotations

RRF_K = 60  # valor habitual: suaviza la diferencia entre las primeras posiciones


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Une rankings de ids (el mejor primero). Devuelve ``(id, puntuación)`` de mayor a menor;
    a igualdad gana el que apareció antes (primero en el primer ranking)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, id_ in enumerate(ranking, start=1):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: -item[1])  # sorted es estable
