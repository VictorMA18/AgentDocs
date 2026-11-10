"""Validación con mermaid-cli: se prueba con un ``mmdc`` falso (script de shell) y, si existe, con el real."""

import stat
from pathlib import Path

import pytest

from techdoc_agent import config
from techdoc_agent.core.tools import ToolRegistry
from techdoc_agent.core.tools_outputs import output_tools
from techdoc_agent.outputs.mermaid_cli import validate_with_cli

VALID = "flowchart TD\n    A[Encolar] --> B[Procesar]"


def fake_mmdc(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "mmdc"
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def use(monkeypatch: pytest.MonkeyPatch, exe: Path, **extra: str) -> None:
    env = {"MERMAID_VALIDATE": "cli", "MERMAID_CLI_PATH": str(exe), **extra}
    monkeypatch.setattr(config, "settings", config.load_settings(env))


def test_accepts_when_mmdc_succeeds_and_receives_the_code_in_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = tmp_path / "visto.txt"
    # $2 es el archivo de entrada (-i <archivo>): el script lo copia para comprobar que el código llegó por archivo
    use(monkeypatch, fake_mmdc(tmp_path, f'cp "$2" "{seen}"; touch "$4"; exit 0'))
    assert validate_with_cli(VALID) == []
    assert seen.read_text(encoding="utf-8") == VALID


def test_code_with_shell_metacharacters_is_never_executed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "pwned"
    use(monkeypatch, fake_mmdc(tmp_path, "exit 0"))
    assert validate_with_cli(f'flowchart TD\n    A["$(touch {marker})"] --> B; touch {marker}') == []
    assert not marker.exists()


def test_parse_error_returns_the_parser_message_without_the_node_stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = ('echo "Error: Parse error on line 2:" >&2; echo "...[Encolar --> B" >&2; '
            'echo "Expecting \'SQE\', got \'NODE_STRING\'" >&2; echo "    at Parser.parseError (file.js:1:1)" >&2; exit 1')
    use(monkeypatch, fake_mmdc(tmp_path, body))
    [message] = validate_with_cli("flowchart TD\n    A[Encolar --> B")
    assert "Parse error on line 2" in message and "Expecting" in message and "at Parser" not in message


def test_environment_failures_are_not_blamed_on_the_diagram(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, fake_mmdc(tmp_path, 'echo "Error: Failed to launch the browser process!" >&2; exit 1'))
    assert validate_with_cli(VALID) is None


def test_missing_binary_and_timeout_mean_could_not_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, tmp_path / "no-existe")
    assert validate_with_cli(VALID) is None
    use(monkeypatch, fake_mmdc(tmp_path, "sleep 5"), MERMAID_TIMEOUT_S="1")
    assert validate_with_cli(VALID) is None


def test_puppeteer_config_is_passed_when_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = tmp_path / "args.txt"
    use(monkeypatch, fake_mmdc(tmp_path, f'echo "$@" > "{args}"; exit 0'), MERMAID_PUPPETEER_CONFIG="/x/p.json")
    validate_with_cli(VALID)
    assert "-p /x/p.json" in args.read_text(encoding="utf-8") and "--quiet" in args.read_text(encoding="utf-8")


REAL_STDERR = """
Error: Parse error on line 4:
...   A[Encolar --> B
---------------------^
Expecting 'SQE', 'DOUBLECIRCLEEND', got '1'
Parser.parseError (https://mermaid-cli-intercept.invalid/home/victorma/proyecto/tools/mermaid/node_modules/mermaid/dist/x.mjs:1561:21)
    at #evaluate (file:///home/victorma/proyecto/tools/mermaid/node_modules/puppeteer-core/lib/x.js:402:19)
"""


def test_real_mmdc_output_is_cut_before_the_internal_stack_and_leaks_no_local_paths(tmp_path: Path,
                                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "salida.txt"
    script.write_text(REAL_STDERR, encoding="utf-8")
    use(monkeypatch, fake_mmdc(tmp_path, f'cat "{script}" >&2; exit 1'))
    [message] = validate_with_cli("x")
    assert "Parse error on line 4" in message and "Expecting" in message
    assert "/home/" not in message and "node_modules" not in message and "intercept" not in message


# --- integración en la herramienta ---


def registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(output_tools(tmp_path / "out"))


ARGS = {"tipo": "flujo", "titulo": "Cola", "codigo": VALID}


def test_tool_returns_the_mermaid_error_to_the_model_and_saves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, fake_mmdc(tmp_path, 'echo "Error: Parse error on line 2" >&2; exit 1'))
    text, is_error = registry(tmp_path).dispatch("generar_diagrama", ARGS)
    assert is_error and "Mermaid rechazó el diagrama" in text and "Parse error on line 2" in text
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_tool_falls_back_to_the_heuristic_when_mmdc_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, tmp_path / "no-existe")
    text, is_error = registry(tmp_path).dispatch("generar_diagrama", ARGS)
    assert not is_error and "guardado como" in text


def test_heuristic_mode_never_calls_mmdc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "llamado"
    exe = fake_mmdc(tmp_path, f'touch "{marker}"; exit 1')
    monkeypatch.setattr(config, "settings", config.load_settings({"MERMAID_VALIDATE": "heuristic", "MERMAID_CLI_PATH": str(exe)}))
    assert not registry(tmp_path).dispatch("generar_diagrama", ARGS)[1]
    assert not marker.exists()


def test_invalid_mode_is_rejected_at_startup() -> None:
    with pytest.raises(ValueError, match="MERMAID_VALIDATE debe ser uno de"):
        config.load_settings({"MERMAID_VALIDATE": "mucho"})


# --- con el mmdc real, si está instalado ---

REAL = Path("tools/mermaid/node_modules/.bin/mmdc")


@pytest.mark.skipif(not REAL.is_file(), reason="mermaid-cli no está instalado (tools/mermaid)")
def test_real_mmdc_accepts_a_valid_diagram_and_rejects_a_broken_one(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, REAL.resolve(), MERMAID_PUPPETEER_CONFIG=str(Path("tools/mermaid/puppeteer-config.json").resolve()))
    assert validate_with_cli(VALID) == []
    errors = validate_with_cli("flowchart TD\n    A[Encolar --> B")
    assert errors and errors != [""]
