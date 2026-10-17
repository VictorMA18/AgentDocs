"""Recorte de memoria por resumen dentro del agente (LLM falso)."""

import json
from pathlib import Path

import pytest
from fakes import FakeLLMClient, final

from techdoc_agent import config
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.tools import ToolRegistry

BASE = "PROMPT BASE"


@pytest.fixture(autouse=True)
def _env(logs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # umbral minúsculo: 100 tokens estimados, se conservan 2 turnos
    monkeypatch.setattr(config, "settings", config.load_settings(
        {"LOGS_DIR": str(logs_dir), "MEMORY_MAX_TOKENS": "100", "MEMORY_KEEP_TURNS": "2"}))


def make(script: list) -> tuple[Agent, FakeLLMClient]:
    llm = FakeLLMClient(script)
    return Agent(llm, ToolRegistry(), Memory(), BASE), llm


def long_turn(agent: Agent, n: int) -> None:
    agent.run("s", f"pregunta {n} " + "x" * 300)


def events(logs_dir: Path) -> list[dict]:
    return [json.loads(line) for f in logs_dir.glob("agent-*.jsonl") for line in f.read_text().splitlines()]


def test_below_threshold_no_summary_call() -> None:
    agent, llm = make([final("a"), final("b")])
    agent.run("s", "hola")
    agent.run("s", "otra")
    assert len(llm.seen) == 2 and agent.memory.summary("s") == ""


def test_over_threshold_summarizes_old_turns_and_keeps_recent_ones(logs_dir: Path) -> None:
    agent, llm = make([final("r1"), final("r2"), final("r3"), final("RESUMEN"), final("r4")])
    for n in (1, 2, 3):
        long_turn(agent, n)
    long_turn(agent, 4)  # aquí se compacta: 3 turnos > keep=2 y supera el umbral
    summary_call = llm.seen[3]
    assert "pregunta 1" in summary_call[0]["content"] and llm.systems[3] != BASE
    last_call_msgs = llm.seen[4]
    # turnos 2 y 3 íntegros + el mensaje nuevo; el turno 1 ya no está
    assert [m["role"] for m in last_call_msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert last_call_msgs[0]["content"].startswith("pregunta 2")
    assert llm.systems[4].startswith(BASE) and "<resumen_conversacion>\nRESUMEN\n" in llm.systems[4]
    done = [e for e in events(logs_dir) if e["event"] == "memory_compacted"]
    assert len(done) == 1 and done[0]["turns_summarized"] == 1
    assert done[0]["chars_after"] < done[0]["chars_before"]


def test_second_compaction_is_cumulative() -> None:
    agent, llm = make([final("r"), final("r"), final("r"), final("RES1"), final("r"),
                       final("RES2"), final("r")])
    for n in range(1, 6):
        long_turn(agent, n)
    resumenes = [c[0]["content"] for c in llm.seen if "<resumen_previo>" in c[0]["content"]]
    assert "(vacío)" in resumenes[0] and "RES1" in resumenes[1]
    assert agent.memory.summary("s") == "RES2"


def test_summary_failure_does_not_break_the_turn(logs_dir: Path) -> None:
    agent, llm = make([final("r"), final("r"), final("r"), LLMError("caído"), final("r4")])
    for n in (1, 2, 3):
        long_turn(agent, n)
    long_turn(agent, 4)  # no lanza: el turno se completa sin recorte
    assert agent.memory.summary("s") == "" and agent.memory.turn_count("s") == 4
    assert any(e["event"] == "memory_compact_error" for e in events(logs_dir))


def test_rollback_after_llm_error_keeps_turn_marks_consistent() -> None:
    agent, _ = make([final("r1"), LLMError("caído"), final("r2")])
    agent.run("s", "uno")
    with pytest.raises(LLMError):
        agent.run("s", "dos")
    assert agent.memory.turn_count("s") == 1 and len(agent.memory.get("s")) == 2
    agent.run("s", "tres")
    assert agent.memory.turn_count("s") == 2


def test_new_conversation_forgets_summary() -> None:
    agent, llm = make([final("r"), final("r"), final("r"), final("RES"), final("r"), final("nueva")])
    for n in (1, 2, 3, 4):
        long_turn(agent, n)
    agent.memory.clear("s")
    agent.run("s", "hola")
    assert llm.systems[-1] == BASE
