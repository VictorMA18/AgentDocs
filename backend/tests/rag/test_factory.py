"""Tests de la fábrica de almacenes."""

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from techdoc_agent import config
from techdoc_agent.rag.factory import build_store
from techdoc_agent.rag.store_json import JsonVectorStore


def settings(tmp_path: Path, store: str) -> config.Settings:
    return dataclasses.replace(config.settings, data_dir=tmp_path, vector_store=store)


def test_json_is_built_in_index_dir(tmp_path: Path) -> None:
    store = build_store(settings(tmp_path, "json"))
    assert isinstance(store, JsonVectorStore) and store.index_dir == tmp_path / "index"


def test_chroma_is_built_in_its_subfolder(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    from techdoc_agent.rag.store_chroma import ChromaVectorStore

    store = build_store(settings(tmp_path, "chroma"))
    assert isinstance(store, ChromaVectorStore) and store.index_dir == tmp_path / "index" / "chroma"


def test_unknown_store_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="VECTOR_STORE='faiss'.*json, chroma"):
        build_store(settings(tmp_path, "faiss"))


def test_json_mode_does_not_import_chromadb(tmp_path: Path) -> None:
    code = (
        "import dataclasses, sys\n"
        "from pathlib import Path\n"
        "from techdoc_agent import config\n"
        "from techdoc_agent.rag.factory import build_store\n"
        f"s = dataclasses.replace(config.settings, data_dir=Path({str(tmp_path)!r}), vector_store='json')\n"
        "build_store(s)\n"
        "assert 'chromadb' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
