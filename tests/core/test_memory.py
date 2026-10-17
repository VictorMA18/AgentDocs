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


def add_turn(memory: Memory, sid: str, n: int) -> None:
    memory.mark_turn(sid)
    memory.get(sid).append({"role": "user", "content": f"pregunta {n}"})
    memory.get(sid).append({"role": "assistant", "content": f"respuesta {n}"})


def test_turns_are_counted_and_last_one_can_be_dropped() -> None:
    memory = Memory()
    add_turn(memory, "a", 1)
    add_turn(memory, "a", 2)
    assert memory.turn_count("a") == 2
    memory.drop_last_turn("a")
    assert memory.turn_count("a") == 1 and len(memory.get("a")) == 2


def test_compact_replaces_old_turns_and_keeps_the_last_ones() -> None:
    memory = Memory()
    for n in range(1, 5):
        add_turn(memory, "a", n)
    assert [m["content"] for m in memory.old_messages("a", 2)] == [
        "pregunta 1", "respuesta 1", "pregunta 2", "respuesta 2"]
    memory.compact("a", "resumen", keep_turns=2)
    assert memory.summary("a") == "resumen" and memory.turn_count("a") == 2
    assert [m["content"] for m in memory.get("a")] == [
        "pregunta 3", "respuesta 3", "pregunta 4", "respuesta 4"]
    add_turn(memory, "a", 5)
    memory.drop_last_turn("a")  # las marcas siguen alineadas tras compactar
    assert len(memory.get("a")) == 4


def test_nothing_to_compact_when_turns_do_not_exceed_keep() -> None:
    memory = Memory()
    add_turn(memory, "a", 1)
    assert memory.old_messages("a", 3) == []
    memory.compact("a", "x", 3)
    assert memory.summary("a") == "" and len(memory.get("a")) == 2


def test_estimated_tokens_counts_chars_over_four_and_summary() -> None:
    memory = Memory()
    memory.get("a").append({"role": "user", "content": "x" * 400})
    assert memory.estimated_tokens("a") == 100


def test_clear_also_drops_summary_and_turn_marks() -> None:
    memory = Memory()
    for n in range(1, 4):
        add_turn(memory, "a", n)
    memory.compact("a", "resumen", 1)
    memory.clear("a")
    assert memory.summary("a") == "" and memory.turn_count("a") == 0 and memory.get("a") == []
