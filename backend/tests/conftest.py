"""Fixtures compartidas por los tests."""

import dataclasses
from pathlib import Path

import pytest

from techdoc_agent import config


@pytest.fixture
def logs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige los logs a una carpeta temporal para no ensuciar ``logs/``."""
    target = tmp_path / "logs"
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, logs_dir=target)
    )
    return target
