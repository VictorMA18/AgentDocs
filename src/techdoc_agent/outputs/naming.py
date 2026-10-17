"""Nombres de archivo generados por el sistema (slug + id corto), nunca rutas del modelo."""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

MAX_SLUG = 40


def slugify(text: str) -> str:
    """Minúsculas, sin acentos, solo ``[a-z0-9-]``; vacío si no queda nada útil."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:MAX_SLUG].strip("-")


def write_unique(directory: Path, prefix: str, title: str, extension: str, content: str) -> str:
    """Guarda ``content`` como ``<prefix>-<slug>-<id>.<ext>`` dentro de ``directory``.

    Devuelve solo el nombre del archivo. Usa creación exclusiva: nunca pisa otro archivo.
    """
    directory.mkdir(parents=True, exist_ok=True)
    slug = slugify(title)
    base = f"{prefix}-{slug}" if slug else prefix
    for _ in range(20):
        name = f"{base}-{uuid.uuid4().hex[:4]}.{extension}"
        try:
            with (directory / name).open("x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            continue
        return name
    raise RuntimeError("No se pudo generar un nombre de archivo único")
