"""Tests del cliente LLM (el CLI real nunca se ejecuta)."""

import json
import subprocess
from typing import Any

import pytest

from techdoc_agent.core.llm import (
    ClaudeCliClient,
    LLMError,
    LLMProtocolError,
    ToolCall,
    parse_output,
)
from techdoc_agent.core.tools import ToolSpec

USAGE = {
    "input_tokens": 2,
    "cache_creation_input_tokens": 1000,
    "cache_read_input_tokens": 50,
    "output_tokens": 30,
}


def cli_output(structured: Any, **extra: Any) -> str:
    return json.dumps({"structured_output": structured, "usage": USAGE, **extra})


# --- parse_output ---


def test_parse_final_answer() -> None:
    reply = parse_output(cli_output({"accion": "responder", "texto": "Hola"}))
    assert reply.text == "Hola" and reply.tool_calls == []
    assert reply.input_tokens == 1052 and reply.output_tokens == 30
    assert json.loads(reply.raw)["accion"] == "responder"


def test_parse_tool_calls() -> None:
    structured = {
        "accion": "herramientas",
        "llamadas": [
            {"id": "c1", "nombre": "obtener_hora", "args": {}},
            {"id": "c2", "nombre": "sumar", "args": {"a": 17, "b": 25}},
        ],
    }
    reply = parse_output(cli_output(structured))
    assert reply.text is None
    assert reply.tool_calls == [
        ToolCall("c1", "obtener_hora", {}),
        ToolCall("c2", "sumar", {"a": 17, "b": 25}),
    ]


@pytest.mark.parametrize(
    "structured",
    [
        {"accion": "responder"},
        {"accion": "responder", "texto": "  "},
        {"accion": "herramientas"},
        {"accion": "herramientas", "llamadas": []},
        {"accion": "herramientas", "llamadas": [{"id": "c1", "nombre": "x"}]},
        {"accion": "herramientas", "llamadas": [{"id": 1, "nombre": "x", "args": {}}]},
        {"accion": "otra"},
        ["no", "es", "objeto"],
    ],
)
def test_incoherent_structured_output_is_protocol_error(structured: Any) -> None:
    with pytest.raises(LLMProtocolError) as exc:
        parse_output(cli_output(structured))
    assert exc.value.raw  # el bucle lo necesita para el historial


def test_missing_structured_output_is_protocol_error() -> None:
    with pytest.raises(LLMProtocolError):
        parse_output(json.dumps({"result": "texto libre", "usage": USAGE}))


def test_cli_error_flag_is_llm_error_not_protocol_error() -> None:
    with pytest.raises(LLMError) as exc:
        parse_output(json.dumps({"is_error": True, "result": "sesión caducada"}))
    assert not isinstance(exc.value, LLMProtocolError)
    assert "sesión caducada" in str(exc.value)


def test_non_json_stdout_is_llm_error() -> None:
    with pytest.raises(LLMError, match="no es JSON"):
        parse_output("Segmentation fault")


# --- construcción del prompt ---

TOOLS = [ToolSpec("sumar", "Suma dos números.", {"type": "object"})]


def test_system_includes_protocol_and_tools() -> None:
    system = ClaudeCliClient._build_system("Eres un asistente.", TOOLS)
    assert system.startswith("Eres un asistente.")
    assert '"accion": "responder"' in system
    assert '"nombre": "sumar"' in system


def test_system_without_tools_says_so() -> None:
    assert "No hay herramientas" in ClaudeCliClient._build_system("x", [])


def test_render_messages_is_a_transcript() -> None:
    text = ClaudeCliClient._render_messages(
        [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": '{"accion":"responder","texto":"qué tal"}'},
            {"role": "user", "content": "bien"},
        ]
    )
    assert text.startswith("[usuario]\nhola\n\n[asistente]\n")
    assert "[usuario]\nbien" in text
    assert text.rstrip().endswith("(responde con el objeto JSON del protocolo)")


# --- ejecución del proceso (subprocess simulado) ---


class FakeRun:
    def __init__(self, stdout: str = "", returncode: int = 0, error: Exception | None = None):
        self.stdout, self.returncode, self.error = stdout, returncode, error
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, kwargs))
        if self.error:
            raise self.error
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "stderr simulado")


def client() -> ClaudeCliClient:
    return ClaudeCliClient(model="claude-haiku-5-5", cli_path="claude", timeout_s=7)


def test_complete_builds_expected_command(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun(cli_output({"accion": "responder", "texto": "ok"}))
    monkeypatch.setattr(subprocess, "run", fake)

    reply = client().complete("sistema", [{"role": "user", "content": "hola"}], TOOLS)

    assert reply.text == "ok"
    cmd, kwargs = fake.calls[0]
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--model") + 1] == "claude-haiku-5-5"
    assert cmd[cmd.index("--tools") + 1] == ""
    for flag in ("--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"):
        assert flag in cmd
    assert json.loads(cmd[cmd.index("--json-schema") + 1])["required"] == ["accion"]
    assert "[usuario]\nhola" in kwargs["input"]  # historial por stdin
    assert kwargs["timeout"] == 7


def test_timeout_is_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", FakeRun(error=subprocess.TimeoutExpired("claude", 7)))
    with pytest.raises(LLMError, match="tiempo máximo"):
        client().complete("s", [{"role": "user", "content": "x"}], [])


def test_missing_cli_is_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", FakeRun(error=FileNotFoundError()))
    with pytest.raises(LLMError, match="CLAUDE_CLI_PATH"):
        client().complete("s", [{"role": "user", "content": "x"}], [])


def test_nonzero_exit_is_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", FakeRun(returncode=1))
    with pytest.raises(LLMError, match="código 1"):
        client().complete("s", [{"role": "user", "content": "x"}], [])
