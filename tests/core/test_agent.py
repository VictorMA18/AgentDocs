"""Tests del bucle del agente con un LLM falso (sin ejecutar el CLI)."""

import json
from pathlib import Path

import pytest
from fakes import FakeLLMClient, calls, final, toy_tools

from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMError, LLMProtocolError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.tools import ToolRegistry


@pytest.fixture(autouse=True)
def _isolated_logs(logs_dir: Path) -> None:
    """Ningún test de este módulo escribe en ``logs/`` real."""


def make_agent(script: list, max_iterations: int = 8) -> tuple[Agent, FakeLLMClient]:
    llm = FakeLLMClient(script)
    return Agent(llm, ToolRegistry(toy_tools()), Memory(), max_iterations=max_iterations), llm


def test_direct_answer_without_tools() -> None:
    agent, llm = make_agent([final("Hola, ¿en qué te ayudo?")])
    result = agent.run("s1", "hola")
    assert result.text == "Hola, ¿en qué te ayudo?"
    assert result.tool_calls == [] and result.iterations == 1 and not result.truncated
    assert len(llm.seen) == 1


def test_single_tool_call_then_answer() -> None:
    agent, llm = make_agent([calls(("c1", "sumar", {"a": 17, "b": 25})), final("Son 42.")])
    result = agent.run("s1", "¿cuánto es 17+25?")
    assert result.text == "Son 42." and result.iterations == 2
    assert [(t.name, t.is_error) for t in result.tool_calls] == [("sumar", False)]
    assert result.tool_calls[0].result  # conserva el texto que devolvió la herramienta
    # el modelo ve el resultado en un mensaje 'user'
    last = llm.seen[1][-1]
    assert last["role"] == "user"
    assert '<resultado_herramienta id="c1" error="false">42</resultado_herramienta>' in last["content"]


def test_two_tools_in_one_turn_answered_in_one_message() -> None:
    agent, llm = make_agent(
        [calls(("c1", "obtener_hora", {}), ("c2", "sumar", {"a": 1, "b": 2})), final("listo")]
    )
    result = agent.run("s1", "hora y suma")
    assert [t.name for t in result.tool_calls] == ["obtener_hora", "sumar"]
    results_msg = llm.seen[1][-1]["content"]
    assert 'id="c1"' in results_msg and 'id="c2"' in results_msg
    roles = [m["role"] for m in llm.seen[1]]
    assert roles == ["user", "assistant", "user"]  # un solo mensaje con ambos resultados


def test_failing_tool_does_not_break_the_loop() -> None:
    agent, llm = make_agent(
        [calls(("c1", "sumar", {"a": 10**13, "b": 1})),
         calls(("c2", "sumar", {"a": 1, "b": 1})),
         final("Son 2.")]
    )
    result = agent.run("s1", "suma")
    assert result.text == "Son 2."
    assert [t.is_error for t in result.tool_calls] == [True, False]
    assert 'error="true"' in llm.seen[1][-1]["content"]
    assert "fuera de rango" in llm.seen[1][-1]["content"]


def test_unknown_tool_is_reported_to_the_model() -> None:
    agent, llm = make_agent([calls(("c1", "no_existe", {})), final("no pude")])
    result = agent.run("s1", "x")
    assert result.tool_calls[0].is_error
    assert "desconocida" in llm.seen[1][-1]["content"]


def test_iteration_limit_truncates() -> None:
    script = [calls((f"c{i}", "obtener_hora", {})) for i in range(10)]
    agent, llm = make_agent(script, max_iterations=3)
    result = agent.run("s1", "bucle")
    assert result.truncated and result.iterations == 3
    assert len(llm.seen) == 3  # nunca excede el tope
    assert "3 pasos" in result.text
    assert agent.memory.get("s1")[-1]["role"] == "assistant"  # el historial queda consistente


def test_protocol_error_is_sent_back_to_the_model() -> None:
    agent, llm = make_agent([LLMProtocolError("sin 'texto'.", raw="{}"), final("ok")])
    result = agent.run("s1", "hola")
    assert result.text == "ok" and result.iterations == 2
    second = llm.seen[1]
    assert second[-2] == {"role": "assistant", "content": "{}"}
    assert "Error de protocolo" in second[-1]["content"]


def test_llm_error_propagates_and_rolls_back_the_turn() -> None:
    agent, _ = make_agent([LLMError("timeout")])
    with pytest.raises(LLMError):
        agent.run("s1", "hola")
    assert agent.memory.get("s1") == []


def test_history_persists_across_turns_in_same_session() -> None:
    agent, llm = make_agent([final("uno"), final("dos")])
    agent.run("s1", "primero")
    agent.run("s1", "segundo")
    assert [m["role"] for m in llm.seen[1]] == ["user", "assistant", "user"]
    assert llm.seen[1][0]["content"] == "primero"


def test_sessions_do_not_share_history() -> None:
    agent, llm = make_agent([final("a"), final("b")])
    agent.run("s1", "hola")
    agent.run("s2", "hola")
    assert len(llm.seen[1]) == 1


def test_tokens_are_accumulated() -> None:
    agent, _ = make_agent([calls(("c1", "obtener_hora", {}), input_tokens=100), final("ok", 200, 7)])
    result = agent.run("s1", "x")
    assert result.input_tokens == 300 and result.output_tokens == 12


def test_every_step_is_logged(logs_dir: Path) -> None:
    agent, _ = make_agent([calls(("c1", "sumar", {"a": 1, "b": 2})), final("3")])
    agent.run("s1", "suma secreta")
    lines = next(logs_dir.glob("agent-*.jsonl")).read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    assert [e["event"] for e in events] == ["user_message", "llm_response", "tool_call", "llm_response"]
    tool_event = events[2]
    assert tool_event["tool"] == "sumar" and tool_event["args"] == {"a": 1, "b": 2}
    assert tool_event["is_error"] is False and "duration_ms" in tool_event
    assert events[1]["input_tokens"] == 10 and events[1]["iter"] == 1
    assert "suma secreta" not in "\n".join(lines)  # solo se registra el tamaño del mensaje


# --- el modelo intenta una llamada nativa y lo cuenta como "herramienta no disponible" ---

NATIVE = "No pude guardarlo: la herramienta no está disponible (error \"No such tool available\")."


def test_claim_that_a_tool_is_unavailable_is_sent_back_once_for_correction(logs_dir) -> None:
    agent, llm = make_agent([
        final(NATIVE),
        calls(("c1", "sumar", {"a": 1, "b": 2})),
        final("Son 3."),
    ])
    result = agent.run("s1", "suma 1+2")
    assert result.text == "Son 3." and result.iterations == 3
    assert [t.name for t in result.tool_calls] == ["sumar"]
    hint = llm.seen[1][-1]["content"]  # lo que vio el modelo tras su respuesta errónea
    assert hint.startswith("Error de protocolo") and '"accion": "herramientas"' in hint
    assert llm.seen[1][-2]["content"].count("No such tool available") == 1  # su respuesta quedó en el historial
    events = [json.loads(line)["event"] for f in logs_dir.glob("*.jsonl") for line in f.read_text().splitlines()]
    assert "native_tool_attempt" in events


def test_the_correction_is_not_repeated_so_it_cannot_loop(logs_dir) -> None:
    agent, llm = make_agent([final(NATIVE), final(NATIVE)])
    result = agent.run("s1", "suma 1+2")
    assert result.text == NATIVE and result.iterations == 2 and len(llm.seen) == 2


def test_normal_answers_are_never_touched_by_the_check(logs_dir) -> None:
    agent, llm = make_agent([final("Las herramientas están disponibles; son 3.")])
    assert agent.run("s1", "hola").iterations == 1 and len(llm.seen) == 1
