"""Configuración del proyecto leída de variables de entorno.

Es el único módulo que lee el entorno: el resto importa ``settings``.
Las variables y sus valores por defecto están documentados en ``.env.example``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable del agente, ya convertida a sus tipos."""

    # --- LLM (CLI de Claude Code) ---
    model: str
    claude_cli_path: str
    llm_timeout_s: int
    max_agent_iterations: int

    # --- RAG ---
    vector_store: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    top_k_default: int
    min_score: float

    # --- Rutas ---
    data_dir: Path
    outputs_dir: Path
    logs_dir: Path
    skills_dir: Path
    active_skill: str

    # --- Seguridad / límites ---
    max_upload_mb: int
    allowed_extensions: tuple[str, ...]
    allowed_ingest_dir: Path

    # --- Evaluaciones ---
    eval_min_pass: float


def _get_str(env: Mapping[str, str], name: str, default: str) -> str:
    """Devuelve la variable sin espacios, o el valor por defecto si está vacía."""
    value = env.get(name, "").strip()
    return value or default


def _get_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _get_str(env, name, str(default))
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} debe ser un entero, se recibió {raw!r}") from None


def _get_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _get_str(env, name, str(default))
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} debe ser un número, se recibió {raw!r}") from None


def _get_list(env: Mapping[str, str], name: str, default: str) -> tuple[str, ...]:
    """Lista separada por comas, normalizada a minúsculas y sin vacíos."""
    raw = _get_str(env, name, default)
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _get_path(env: Mapping[str, str], name: str, default: str) -> Path:
    return Path(_get_str(env, name, default))


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Construye la configuración.

    Si ``env`` es ``None`` se carga ``.env`` (sin pisar variables ya definidas)
    y se usa ``os.environ``. Los tests pasan un diccionario para aislarse del
    entorno real.
    """
    if env is None:
        load_dotenv()
        env = os.environ

    return Settings(
        model=_get_str(env, "LLM_MODEL", "claude-haiku-5-5"),
        claude_cli_path=_get_str(env, "CLAUDE_CLI_PATH", "claude"),
        llm_timeout_s=_get_int(env, "LLM_TIMEOUT_S", 120),
        max_agent_iterations=_get_int(env, "MAX_AGENT_ITERATIONS", 8),
        vector_store=_get_str(env, "VECTOR_STORE", "json"),
        embedding_model=_get_str(
            env, "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        ),
        chunk_size=_get_int(env, "CHUNK_SIZE", 700),
        chunk_overlap=_get_int(env, "CHUNK_OVERLAP", 100),
        top_k_default=_get_int(env, "TOP_K_DEFAULT", 5),
        min_score=_get_float(env, "MIN_SCORE", 0.25),
        data_dir=_get_path(env, "DATA_DIR", "./data"),
        outputs_dir=_get_path(env, "OUTPUTS_DIR", "./outputs"),
        logs_dir=_get_path(env, "LOGS_DIR", "./logs"),
        skills_dir=_get_path(env, "SKILLS_DIR", "./skills"),
        active_skill=_get_str(env, "ACTIVE_SKILL", "documentacion-tecnica"),
        max_upload_mb=_get_int(env, "MAX_UPLOAD_MB", 10),
        allowed_extensions=_get_list(
            env,
            "ALLOWED_EXTENSIONS",
            ".md,.txt,.pdf,.py,.js,.ts,.java,.json,.yaml,.yml",
        ),
        allowed_ingest_dir=_get_path(env, "ALLOWED_INGEST_DIR", "./data/documents"),
        eval_min_pass=_get_float(env, "EVAL_MIN_PASS", 0.8),
    )


settings = load_settings()
