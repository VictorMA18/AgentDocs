"""Tests de las transcripciones de conversaciones."""

import json
from pathlib import Path

import pytest

from techdoc_agent.core.transcripts import MAX_LISTED, TITLE_CHARS, Transcripts


@pytest.fixture(autouse=True)
def _isolated_logs(logs_dir: Path) -> None:
    """Los tests no escriben en ``logs/`` real."""


def turn(message: str = "hola", reply: str = "¿qué tal?") -> dict:
    return {"message": message, "reply": reply, "tool_calls": [], "artifacts": [],
            "usage": {"input_tokens": 1, "output_tokens": 2}, "truncated": False}


@pytest.fixture
def transcripts(tmp_path: Path) -> Transcripts:
    return Transcripts(tmp_path / "conv")


def test_first_turn_creates_the_conversation(transcripts: Transcripts) -> None:
    transcripts.append("sesion-1", turn("¿Cuál es la concurrencia por defecto?"))
    data = transcripts.get("sesion-1")
    assert data["id"] == "sesion-1" and data["title"] == "¿Cuál es la concurrencia por defecto?"
    [saved] = data["turns"]
    assert saved["reply"] == "¿qué tal?" and saved["usage"] == {"input_tokens": 1, "output_tokens": 2}
    assert "ts" in saved and data["created"] <= data["updated"]


def test_more_turns_are_appended_and_the_title_stays(transcripts: Transcripts) -> None:
    transcripts.append("sesion-1", turn("primera"))
    transcripts.append("sesion-1", turn("segunda"))
    data = transcripts.get("sesion-1")
    assert [t["message"] for t in data["turns"]] == ["primera", "segunda"] and data["title"] == "primera"


def test_long_titles_are_shortened_and_whitespace_collapsed(transcripts: Transcripts) -> None:
    transcripts.append("sesion-1", turn("palabra   " * 30 + "\n fin"))
    title = transcripts.get("sesion-1")["title"]
    assert len(title) <= TITLE_CHARS and title.endswith("…") and "  " not in title


def test_unknown_conversation_is_none(transcripts: Transcripts) -> None:
    assert transcripts.get("no-existe") is None and transcripts.list() == []


def test_list_is_newest_first_without_the_turns(transcripts: Transcripts, tmp_path: Path) -> None:
    transcripts.append("vieja-1", turn("antigua"))
    transcripts.append("nueva-1", turn("reciente"))
    transcripts.append("nueva-1", turn("otra"))
    for name, age in (("vieja-1", 100), ("nueva-1", 0)):  # fechas distintas sin dormir
        path = transcripts.directory / f"{name}.turns.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["updated"] = f"2026-01-01T00:{59 - age // 10:02d}:00+00:00"
        path.write_text(json.dumps(data), encoding="utf-8")
    listing = transcripts.list()
    assert [c["id"] for c in listing] == ["nueva-1", "vieja-1"]
    assert listing[0]["turns"] == 2 and set(listing[0]) == {"id", "title", "updated", "turns"}


def test_list_is_capped(transcripts: Transcripts) -> None:
    for i in range(MAX_LISTED + 5):
        transcripts.append(f"conv-{i:04d}", turn())
    assert len(transcripts.list()) == MAX_LISTED


def test_delete(transcripts: Transcripts) -> None:
    transcripts.append("sesion-1", turn())
    assert transcripts.delete("sesion-1") is True and transcripts.get("sesion-1") is None
    assert transcripts.delete("sesion-1") is False


def test_survives_a_new_instance(transcripts: Transcripts) -> None:
    transcripts.append("sesion-1", turn("hola"))
    assert Transcripts(transcripts.directory).get("sesion-1")["turns"][0]["message"] == "hola"


@pytest.mark.parametrize("sid", ["../x", "a/b", "", "x" * 65, "con espacio", ".."])
def test_unsafe_ids_are_rejected(transcripts: Transcripts, sid: str) -> None:
    for call in (lambda: transcripts.append(sid, turn()), lambda: transcripts.get(sid),
                 lambda: transcripts.delete(sid)):
        with pytest.raises(ValueError, match="session_id"):
            call()
    assert not transcripts.directory.exists()


@pytest.mark.parametrize("content", ["no es json", "[]", json.dumps({"title": "x"}),
                                     json.dumps({"title": "x", "created": "a", "updated": "b", "turns": [1]})])
def test_unreadable_file_is_set_aside(transcripts: Transcripts, content: str) -> None:
    transcripts.directory.mkdir()
    (transcripts.directory / "sesion-1.turns.json").write_text(content, encoding="utf-8")
    assert transcripts.get("sesion-1") is None and transcripts.list() == []
    assert (transcripts.directory / "sesion-1.turns.json.corrupt").exists()
    transcripts.append("sesion-1", turn())  # la conversación empieza de nuevo
    assert len(transcripts.get("sesion-1")["turns"]) == 1


def test_list_ignores_foreign_files(transcripts: Transcripts) -> None:
    transcripts.append("sesion-1", turn())
    (transcripts.directory / "sesion-1.memory.json").write_text("{}", encoding="utf-8")
    (transcripts.directory / "raro nombre.turns.json").write_text("{}", encoding="utf-8")
    assert [c["id"] for c in transcripts.list()] == ["sesion-1"]
    assert not list(transcripts.directory.glob("*.tmp"))
