"""Factoría de proveedores del LLM y su estado (Fase 10, ADR-028)."""

import json

import pytest

from techdoc_agent import config
from techdoc_agent.core import llm_factory
from techdoc_agent.core.llm import ClaudeCliClient
from techdoc_agent.core.llm_factory import build_llm, llm_description, provider_status
from techdoc_agent.core.llm_gemini import GeminiClient


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    def use(env: dict[str, str]) -> None:
        monkeypatch.setattr(config, "settings", config.load_settings(env))
    return use


def test_build_llm_accepts_a_provider_other_than_the_default(settings) -> None:
    settings({"LLM_PROVIDER": "claude", "GEMINI_MODEL": "gemini-x"})
    assert isinstance(build_llm(), ClaudeCliClient)
    assert isinstance(build_llm("gemini"), GeminiClient)
    assert llm_description("gemini") == {"provider": "gemini", "model": "gemini-x"}


def test_unknown_provider_is_rejected(settings) -> None:
    settings({})
    with pytest.raises(ValueError, match="Proveedor desconocido"):
        build_llm("openai")


def test_status_reports_model_default_and_why_a_provider_is_unavailable(settings, monkeypatch) -> None:
    settings({"LLM_PROVIDER": "gemini", "LLM_MODEL": "claude-m", "GEMINI_MODEL": "gemini-m"})
    monkeypatch.setattr(llm_factory.shutil, "which", lambda _path: None)
    claude, gemini = provider_status()
    assert claude == {"id": "claude", "label": "Claude", "model": "claude-m", "available": False,
                      "reason": "No se encontró el CLI de Claude Code (revisa CLAUDE_CLI_PATH).", "default": False}
    assert gemini["available"] is False and "GEMINI_API_KEY" in gemini["reason"] and gemini["default"] is True


def test_status_is_available_with_key_and_cli_and_never_shows_the_key(settings, monkeypatch) -> None:
    secret = "AIzaSy-no-debe-salir"
    settings({"GEMINI_API_KEY": secret})
    monkeypatch.setattr(llm_factory.shutil, "which", lambda path: f"/usr/bin/{path}")
    status = provider_status()
    assert all(p["available"] and p["reason"] is None for p in status)
    assert secret not in json.dumps(status)


def test_the_reason_never_reveals_the_local_cli_path(settings, monkeypatch) -> None:
    settings({"CLAUDE_CLI_PATH": "/home/alguien/.local/bin/claude"})
    monkeypatch.setattr(llm_factory.shutil, "which", lambda _path: None)
    assert "/home/alguien" not in json.dumps(provider_status())
