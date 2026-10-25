"""Búsqueda léxica BM25 hecha a mano (docs/05, modo híbrido).

La búsqueda vectorial compara significados y puede perder un identificador exacto
(``E-4021``, ``ack_batch_window``). BM25 compara palabras: puntúa más un fragmento cuanto más
veces contiene los términos de la consulta (``tf``), cuanto más raros son en el corpus (``idf``)
y cuanto más corto es el fragmento. El índice vive en memoria y se reconstruye a partir de los
fragmentos del almacén: el corpus de este proyecto es pequeño y así no hay nada más que mantener
sincronizado.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from techdoc_agent.rag.store import Chunk

K1 = 1.5  # cuánto crece la puntuación al repetirse un término (saturación)
B = 0.75  # cuánto penaliza los fragmentos más largos que la media

STOPWORDS = frozenset(
    "a al algo como con cual cuales cuando de del donde el ella en es esta este esto la las le lo los me mi "
    "no o para por que se si su sus te tu un una uno unos unas y ya hay son ser fue sobre entre desde "
    "hace hacer puede pueden tiene tienen cuanto cuantos cuanta cuantas the of and to in is for".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
_PARTS = re.compile(r"[-_]")


def fold(text: str) -> str:
    """Minúsculas y sin acentos."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()


def tokenize(text: str) -> list[str]:
    """Palabras en minúsculas y sin acentos. Los compuestos (``ack_batch_window``, ``E-4021``,
    ``drain-timeout``) se guardan enteros **y** partidos: la consulta exacta puntúa más alto que
    una que solo comparte una parte."""
    tokens: list[str] = []
    for word in _TOKEN.findall(fold(text)):
        if len(word) >= 2 and word not in STOPWORDS:
            tokens.append(word)
        if _PARTS.search(word):
            tokens.extend(p for p in _PARTS.split(word) if len(p) >= 2 and p not in STOPWORDS)
    return tokens


class Bm25Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._tf = [Counter(tokenize(c.text)) for c in chunks]
        self._length = [sum(tf.values()) for tf in self._tf]
        self._average = sum(self._length) / len(chunks) if chunks else 0.0
        document_frequency: Counter[str] = Counter()
        for tf in self._tf:
            document_frequency.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in document_frequency.items()}

    def search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        """Fragmentos con puntuación BM25 > 0, de mayor a menor (a igualdad, el orden del índice)."""
        terms = set(tokenize(query))
        if not terms or not self.chunks or top_k <= 0:
            return []
        scored: list[tuple[int, float]] = []
        for i, tf in enumerate(self._tf):
            norm = K1 * (1 - B + B * self._length[i] / self._average) if self._average else K1
            score = sum(self._idf[t] * tf[t] * (K1 + 1) / (tf[t] + norm) for t in terms if t in tf)
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda item: -item[1])  # estable: empata por posición en el índice
        return [(self.chunks[i], score) for i, score in scored[:top_k]]
