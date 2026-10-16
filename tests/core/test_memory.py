"""Tests de la memoria por sesión."""

from techdoc_agent.core.memory import Memory


def test_new_session_starts_empty() -> None:
    assert Memory().get("a") == []


def test_get_returns_the_same_list_so_appends_persist() -> None:
    memory = Memory()
    memory.get("a").append({"role": "user", "content": "hola"})
    assert memory.get("a") == [{"role": "user", "content": "hola"}]


def test_sessions_are_independent() -> None:
    memory = Memory()
    memory.get("a").append({"role": "user", "content": "hola"})
    assert memory.get("b") == []


def test_clear_resets_only_that_session() -> None:
    memory = Memory()
    memory.get("a").append({"role": "user", "content": "x"})
    memory.get("b").append({"role": "user", "content": "y"})
    memory.clear("a")
    assert memory.get("a") == []
    assert len(memory.get("b")) == 1
    memory.clear("no-existe")  # no falla
