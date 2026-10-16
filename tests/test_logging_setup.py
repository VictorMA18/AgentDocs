"""Tests del registro JSONL."""

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from techdoc_agent import config
from techdoc_agent.logging_setup import _log_path, log_event


@pytest.fixture
def logs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige los logs a una carpeta temporal."""
    target = tmp_path / "logs"
    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, logs_dir=target)
    )
    return target


def test_log_path_uses_date() -> None:
    now = datetime(2026, 10, 16, tzinfo=timezone.utc)
    assert _log_path(Path("logs"), now) == Path("logs/agent-20261016.jsonl")


def test_log_event_writes_one_json_line_per_call(logs_dir: Path) -> None:
    log_event(event="tool_call", tool="sumar", args={"a": 1}, is_error=False)
    log_event(event="llm_response", stop_reason="end_turn")

    files = list(logs_dir.glob("agent-*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["event"] == "tool_call"
    assert first["args"] == {"a": 1}
    assert "ts" in first


def test_log_event_keeps_non_ascii_and_serializes_unknown_types(logs_dir: Path) -> None:
    log_event(event="nota", texto="configuración", ruta=Path("data"))
    line = next(logs_dir.glob("agent-*.jsonl")).read_text(encoding="utf-8")
    assert "configuración" in line
    assert json.loads(line)["ruta"] == "data"
