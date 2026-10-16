"""Registro de eventos del agente en formato JSONL.

Cada llamada a ``log_event`` añade una línea JSON a
``<LOGS_DIR>/agent-YYYYMMDD.jsonl`` (formato descrito en docs/04, sección 7).

No registrar el contenido completo de documentos (solo tamaños y fuentes)
ni la API key.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from techdoc_agent import config


def _log_path(logs_dir: Path, now: datetime) -> Path:
    """Ruta del archivo de log del día de ``now``."""
    return logs_dir / f"agent-{now:%Y%m%d}.jsonl"


def log_event(**fields: object) -> None:
    """Escribe un evento como una línea JSON, añadiendo la marca de tiempo ``ts``."""
    now = datetime.now(timezone.utc)
    record = {"ts": now.isoformat(timespec="milliseconds"), **fields}

    path = _log_path(config.settings.logs_dir, now)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
