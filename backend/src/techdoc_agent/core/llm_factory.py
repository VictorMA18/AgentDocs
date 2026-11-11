"""Proveedores del LLM: ``claude`` (por defecto) o ``gemini`` (ADR-024, ADR-028).

Como ``rag/factory.build_store``: los adaptadores (CLI, web, MCP, evaluaciones) piden un ``LLMClient`` y
no saben cuál es. El de Gemini solo se importa si se elige. ``LLM_PROVIDER`` fija el de por defecto; la
API web puede pedir otro en cada turno (``build_llm(provider)``) y consultar cuáles están disponibles.
"""

from __future__ import annotations

import shutil
from typing import Any

from techdoc_agent import config
from techdoc_agent.core.llm import ClaudeCliClient, LLMClient

PROVIDERS: tuple[str, ...] = ("claude", "gemini")
LABELS = {"claude": "Claude", "gemini": "Gemini"}


def _resolve(provider: str | None) -> str:
    chosen = provider or config.settings.llm_provider
    if chosen not in PROVIDERS:
        raise ValueError(f"Proveedor desconocido: {chosen!r}. Usa uno de: {', '.join(PROVIDERS)}.")
    return chosen


def build_llm(provider: str | None = None) -> LLMClient:
    """Cliente del proveedor pedido; sin argumento, el de ``LLM_PROVIDER``."""
    if _resolve(provider) == "gemini":
        from techdoc_agent.core.llm_gemini import GeminiClient

        return GeminiClient()
    return ClaudeCliClient()


def model_for(provider: str | None = None) -> str:
    s = config.settings
    return s.gemini_model if _resolve(provider) == "gemini" else s.model


def llm_description(provider: str | None = None) -> dict[str, str]:
    """Proveedor y modelo (para logs, transcripciones y metadatos de las evaluaciones; nunca la clave)."""
    chosen = _resolve(provider)
    return {"provider": chosen, "model": model_for(chosen)}


def _unavailable_reason(provider: str) -> str | None:
    """Por qué no se puede usar ahora, o ``None``. Solo comprueba lo que se sabe sin llamar al modelo:
    la cuota de Gemini o la sesión de Claude se descubren al usarlo (``LLMUnavailableError``)."""
    s = config.settings
    if provider == "gemini" and not s.gemini_api_key:
        return "Falta GEMINI_API_KEY en backend/.env."
    if provider == "claude" and shutil.which(s.claude_cli_path) is None:
        return "No se encontró el CLI de Claude Code (revisa CLAUDE_CLI_PATH)."  # sin la ruta: va al navegador
    return None


def provider_status() -> list[dict[str, Any]]:
    """Proveedores con su modelo y si se pueden usar. Nunca incluye la clave ni su longitud."""
    default = config.settings.llm_provider
    status = []
    for provider in PROVIDERS:
        reason = _unavailable_reason(provider)
        status.append({
            "id": provider, "label": LABELS[provider], "model": model_for(provider),
            "available": reason is None, "reason": reason, "default": provider == default,
        })
    return status
