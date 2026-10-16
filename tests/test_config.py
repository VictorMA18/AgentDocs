"""Tests de la carga de configuración."""

from pathlib import Path

import pytest

from techdoc_agent.config import load_settings


def test_defaults_when_env_is_empty() -> None:
    s = load_settings({})
    assert s.model == "claude-sonnet-5-5"
    assert s.max_tokens == 2048
    assert s.max_agent_iterations == 8
    assert s.vector_store == "json"
    assert s.min_score == pytest.approx(0.25)
    assert s.logs_dir == Path("./logs")
    assert ".md" in s.allowed_extensions and ".pdf" in s.allowed_extensions
    assert s.anthropic_api_key == ""


def test_env_overrides_defaults() -> None:
    s = load_settings({"MAX_TOKENS": "1000", "ANTHROPIC_MODEL": "otro-modelo"})
    assert s.max_tokens == 1000
    assert s.model == "otro-modelo"


def test_empty_value_falls_back_to_default() -> None:
    assert load_settings({"MAX_TOKENS": "  "}).max_tokens == 2048


def test_allowed_extensions_parsed_as_normalized_tuple() -> None:
    s = load_settings({"ALLOWED_EXTENSIONS": ".MD, .txt,,"})
    assert s.allowed_extensions == (".md", ".txt")


def test_invalid_number_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="MAX_TOKENS"):
        load_settings({"MAX_TOKENS": "abc"})


def test_api_key_not_in_repr() -> None:
    s = load_settings({"ANTHROPIC_API_KEY": "sk-secreta-123"})
    assert "sk-secreta-123" not in repr(s)
