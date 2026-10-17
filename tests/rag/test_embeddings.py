"""Tests de embeddings. El modelo real solo se prueba con RUN_MODEL_TESTS=1."""

import os

import numpy as np
import pytest
from fakes import HashingEmbedder

from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder, normalize


def test_normalize_gives_unit_norm() -> None:
    out = normalize(np.array([[3.0, 4.0], [4.0, 3.0]]))
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert np.allclose(out[0], [0.6, 0.8])


def test_dot_product_of_normalized_vectors_is_cosine() -> None:
    a, b = np.array([3.0, 4.0]), np.array([4.0, 3.0])
    cosine = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
    na, nb = normalize(a), normalize(b)
    assert cosine == pytest.approx(0.96)
    assert float(na @ nb) == pytest.approx(0.96, abs=1e-6)


def test_normalize_zero_vector_stays_zero() -> None:
    assert np.array_equal(normalize(np.zeros((1, 3))), np.zeros((1, 3), dtype=np.float32))


def test_hashing_embedder_is_deterministic_and_normalized() -> None:
    emb = HashingEmbedder()
    a, b = emb.embed_documents(["reintentos de tareas"] * 2)
    assert np.array_equal(a, b)
    assert np.linalg.norm(a) == pytest.approx(1.0, abs=1e-6)
    assert emb.embed_query("x").shape == (emb.dimension,)
    assert emb.embed_documents([]).shape == (0, emb.dimension)


def test_hashing_embedder_similar_texts_score_higher() -> None:
    emb = HashingEmbedder()
    q = emb.embed_query("reintentos")
    close, far = emb.embed_documents(["reintentos de tareas", "instalación con pip"])
    assert q @ close > q @ far


@pytest.mark.skipif(not os.environ.get("RUN_MODEL_TESTS"), reason="descarga el modelo real")
def test_real_model_dimension_and_norm() -> None:
    emb = SentenceTransformerEmbedder()
    vectors = emb.embed_documents(["hola mundo", "retries"])
    assert vectors.shape == (2, emb.dimension) == (2, 384)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
