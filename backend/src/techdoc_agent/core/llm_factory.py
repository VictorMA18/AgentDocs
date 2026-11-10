"""Elige el proveedor del LLM según ``LLM_PROVIDER`` (``claude`` por defecto o ``gemini``; ADR-024).

Como ``rag/factory.build_store``: los adaptadores (CLI, web, MCP, evaluaciones) piden un ``LLMClient`` y
no saben cuál es. El de Gemini solo se importa si se elige.
"""

from __future__ import annotations

from techdoc_agent import config
from techdoc_agent.core.llm import ClaudeCliClient, LLMClient


def build_llm() -> LLMClient:
    if config.settings.llm_provider == "gemini":
        from techdoc_agent.core.llm_gemini import GeminiClient

        return GeminiClient()
    return ClaudeCliClient()


def llm_description() -> dict[str, str]:
    """Proveedor y modelo en uso (para logs y metadatos de las evaluaciones; nunca la clave)."""
    s = config.settings
    model = s.gemini_model if s.llm_provider == "gemini" else s.model
    return {"provider": s.llm_provider, "model": model}
