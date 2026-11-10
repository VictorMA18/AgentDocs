"""Memoria persistente: lo que se guarda, cómo se recupera y cómo falla."""

import json
from pathlib import Path

import pytest
from fakes import FakeLLMClient, calls, final

from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.tools import ToolRegistry

SID = "sesion-1"


@pytest.fixture(autouse=True)
def _isolated_logs(logs_dir: Path) -> None:
    """Los tests no escriben en ``logs/`` real."""


def add_turn(memory: Memory, sid: str, n: int) -> None:
    memory.mark_turn(sid)
    memory.get(sid).append({"role": "user", "content": f"pregunta {n}"})
    memory.get(sid).append({"role": "assistant", "content": f"respuesta {n}"})


def test_roundtrip_between_instances(tmp_path: Path) -> None:
    first = Memory(tmp_path)
    add_turn(first, SID, 1)
    add_turn(first, SID, 2)
    first.save(SID)

    second = Memory(tmp_path)  # "reinicio del servidor"
    assert second.get(SID) == first.get(SID)
    assert second.turn_count(SID) == 2
    assert second.old_messages(SID, 1) == [
        {"role": "user", "content": "pregunta 1"}, {"role": "assistant", "content": "respuesta 1"}]


def test_compacted_state_survives(tmp_path: Path) -> None:
    memory = Memory(tmp_path)
    for n in (1, 2, 3):
        add_turn(memory, SID, n)
    memory.compact(SID, "resumen de lo anterior", keep_turns=1)
    memory.save(SID)

    reopened = Memory(tmp_path)
    assert reopened.summary(SID) == "resumen de lo anterior"
    assert [m["content"] for m in reopened.get(SID)] == ["pregunta 3", "respuesta 3"]
    assert reopened.turn_count(SID) == 1


def test_sessions_are_stored_separately(tmp_path: Path) -> None:
    memory = Memory(tmp_path)
    add_turn(memory, "a-sesion", 1)
    add_turn(memory, "b-sesion", 2)
    memory.save("a-sesion")
    memory.save("b-sesion")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a-sesion.memory.json", "b-sesion.memory.json"]
    assert [m["content"] for m in Memory(tmp_path).get("b-sesion")][0] == "pregunta 2"


def test_empty_session_creates_no_file(tmp_path: Path) -> None:
    memory = Memory(tmp_path)
    memory.get(SID)  # solo consultar
    memory.save(SID)
    memory.save("no-existe")
    assert list(tmp_path.glob("*")) == []


def test_clear_deletes_the_file(tmp_path: Path) -> None:
    memory = Memory(tmp_path)
    add_turn(memory, SID, 1)
    memory.save(SID)
    memory.clear(SID)
    assert list(tmp_path.glob("*")) == [] and Memory(tmp_path).get(SID) == []
    memory.clear("nunca-existio")  # no falla


def test_without_a_folder_nothing_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    memory = Memory()
    add_turn(memory, SID, 1)
    memory.save(SID)
    assert list(tmp_path.glob("**/*")) == []


def test_no_temporary_files_are_left(tmp_path: Path) -> None:
    memory = Memory(tmp_path)
    add_turn(memory, SID, 1)
    memory.save(SID)
    memory.save(SID)
    assert [p.name for p in tmp_path.iterdir()] == [f"{SID}.memory.json"]


@pytest.mark.parametrize("sid", ["../x", "a/b", "", "x" * 65, "con espacio", "..", "a.b"])
def test_unsafe_session_ids_are_rejected_when_persisting(tmp_path: Path, sid: str) -> None:
    memory = Memory(tmp_path)
    with pytest.raises(ValueError, match="session_id"):
        memory.get(sid)
    with pytest.raises(ValueError, match="session_id"):
        memory.clear(sid)
    assert list(tmp_path.glob("**/*")) == []


@pytest.mark.parametrize("content", [
    "esto no es json",
    json.dumps([1, 2, 3]),
    json.dumps({"version": 99, "messages": [], "turn_starts": [], "summary": ""}),
    json.dumps({"version": 1, "messages": [{"role": "robot", "content": "x"}], "turn_starts": [0], "summary": ""}),
    json.dumps({"version": 1, "messages": [{"role": "user", "content": "x"}], "turn_starts": [5], "summary": ""}),
    json.dumps({"version": 1, "messages": [], "turn_starts": [], "summary": 3}),
])
def test_unreadable_file_is_set_aside_and_the_session_starts_empty(tmp_path: Path, content: str) -> None:
    (tmp_path / f"{SID}.memory.json").write_text(content, encoding="utf-8")
    memory = Memory(tmp_path)
    assert memory.get(SID) == [] and memory.summary(SID) == ""
    assert not (tmp_path / f"{SID}.memory.json").exists()
    assert (tmp_path / f"{SID}.memory.json.corrupt").read_text(encoding="utf-8") == content
    add_turn(memory, SID, 1)  # y se puede seguir usando
    memory.save(SID)
    assert Memory(tmp_path).turn_count(SID) == 1


# --- con el agente ---


def make_agent(tmp_path: Path, script: list) -> tuple[Agent, FakeLLMClient]:
    llm = FakeLLMClient(script)
    return Agent(llm, ToolRegistry([]), Memory(tmp_path)), llm


def test_agent_saves_after_each_run(tmp_path: Path) -> None:
    agent, _ = make_agent(tmp_path, [final("uno"), final("dos")])
    agent.run(SID, "primera")
    assert [m["role"] for m in Memory(tmp_path).get(SID)] == ["user", "assistant"]
    agent.run(SID, "segunda")
    assert len(Memory(tmp_path).get(SID)) == 4


def test_agent_continues_after_a_restart(tmp_path: Path) -> None:
    agent, _ = make_agent(tmp_path, [final("Me llamo Claude.")])
    agent.run(SID, "¿cómo te llamas?")

    restarted, llm = make_agent(tmp_path, [final("Te dije que Claude.")])
    restarted.run(SID, "¿y cómo era?")
    first_call = llm.seen[0]
    assert [m["content"] for m in first_call][0] == "¿cómo te llamas?"  # ve lo anterior
    assert first_call[-1] == {"role": "user", "content": "¿y cómo era?"}


def test_failed_turn_is_rolled_back_on_disk_too(tmp_path: Path) -> None:
    agent, _ = make_agent(tmp_path, [final("ok"), LLMError("se cayó")])
    agent.run(SID, "primera")
    with pytest.raises(LLMError):
        agent.run(SID, "segunda")
    on_disk = Memory(tmp_path).get(SID)
    assert [m["content"] for m in on_disk][0] == "primera" and len(on_disk) == 2  # sin 'user' colgado


def test_iteration_limit_state_is_saved(tmp_path: Path) -> None:
    memory = Memory(tmp_path)
    agent = Agent(FakeLLMClient([calls(("c1", "nada", {}))]), ToolRegistry([]), memory, max_iterations=1)
    assert agent.run(SID, "hola").truncated
    assert Memory(tmp_path).turn_count(SID) == 1


def test_disk_failure_does_not_break_the_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agent, _ = make_agent(tmp_path, [final("respuesta")])

    def boom(self: Memory, sid: str) -> None:
        raise OSError("disco lleno")

    monkeypatch.setattr(Memory, "save", boom)
    assert agent.run(SID, "hola").text == "respuesta"
