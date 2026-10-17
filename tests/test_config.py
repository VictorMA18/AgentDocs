"""Tests de la carga de configuración."""

from pathlib import Path

import pytest

from techdoc_agent.config import load_settings


def test_defaults_when_env_is_empty() -> None:
    s = load_settings({})
    assert s.model == "claude-haiku-5-5"
    assert s.claude_cli_path == "claude"
    assert s.llm_timeout_s == 120
    assert s.max_agent_iterations == 8
    assert s.memory_max_tokens == 8000 and s.memory_keep_turns == 3
    assert s.vector_store == "json"
    assert s.min_score == pytest.approx(0.25)
    assert s.logs_dir == Path("./logs")
    assert ".md" in s.allowed_extensions and ".pdf" in s.allowed_extensions


def test_env_overrides_defaults() -> None:
    s = load_settings({"LLM_TIMEOUT_S": "30", "LLM_MODEL": "otro-modelo"})
    assert s.llm_timeout_s == 30
    assert s.model == "otro-modelo"


def test_empty_value_falls_back_to_default() -> None:
    assert load_settings({"LLM_TIMEOUT_S": "  "}).llm_timeout_s == 120


def test_allowed_extensions_parsed_as_normalized_tuple() -> None:
    s = load_settings({"ALLOWED_EXTENSIONS": ".MD, .txt,,"})
    assert s.allowed_extensions == (".md", ".txt")


def test_invalid_number_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="LLM_TIMEOUT_S"):
        load_settings({"LLM_TIMEOUT_S": "abc"})
