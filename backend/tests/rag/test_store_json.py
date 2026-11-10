"""Tests específicos del almacén JSON + numpy (el contrato común está en test_store_contract)."""

import json
from pathlib import Path

import numpy as np
import pytest

from techdoc_agent.rag.store import Chunk
from techdoc_agent.rag.store_json import JsonVectorStore

X, Y, Z = (np.eye(3, dtype=np.float32)[i] for i in range(3))


@pytest.fixture
def store(tmp_path: Path) -> JsonVectorStore:
    chunks = [Chunk(f"{s}#{n}", s, "t", {"chunk_index": n}) for s, n in (("a.md", 0), ("a.md", 1), ("b.md", 0))]
    s = JsonVectorStore(tmp_path / "index")
    s.add(chunks, np.stack([X, Y, Z]))
    return s


def test_files_on_disk_are_readable(store: JsonVectorStore, tmp_path: Path) -> None:
    index = tmp_path / "index"
    data = json.loads((index / "index.json").read_text(encoding="utf-8"))
    assert data["dimension"] == 3 and len(data["chunks"]) == 3
    assert np.load(index / "vectors.npy").shape == (3, 3)
    assert not list(index.glob("*.tmp"))  # sin temporales tras guardar


def test_corrupt_index_is_detected(store: JsonVectorStore, tmp_path: Path) -> None:
    np.save(tmp_path / "index" / "vectors.npy", np.zeros((1, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="corrupto"):
        JsonVectorStore(tmp_path / "index")
