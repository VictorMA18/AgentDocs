"""Lectura de archivos a texto plano, con validación de tipo y tamaño."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from techdoc_agent import config

TEXT_EXTENSIONS = {".md", ".txt"}
CODE_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass
class Document:
    source: str  # nombre del archivo, p. ej. "taskflow.md"
    text: str
    doc_type: str  # "md" | "txt" | "pdf" | "code"
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(path)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except PyPdfError as exc:
        raise ValueError(f"No se pudo leer el PDF {path.name}: {exc}") from None
    return "\n\n".join(p for p in pages if p)


def load_file(
    path: str | Path,
    *,
    allowed: tuple[str, ...] | None = None,
    max_mb: float | None = None,
) -> Document:
    """Lee un archivo. Lanza ``ValueError`` si el tipo o el tamaño no son válidos."""
    path = Path(path)
    allowed = allowed if allowed is not None else config.settings.allowed_extensions
    max_mb = max_mb if max_mb is not None else config.settings.max_upload_mb
    ext = path.suffix.lower()

    if ext not in allowed:
        raise ValueError(f"Extensión no permitida: {ext or '(ninguna)'} ({path.name})")
    if not path.is_file():
        raise ValueError(f"No es un archivo: {path}")
    if path.stat().st_size > max_mb * 1024 * 1024:
        raise ValueError(f"{path.name} supera el tamaño máximo de {max_mb:g} MB")

    if ext == ".pdf":
        text = _read_pdf(path)
        doc = Document(path.name, text, "pdf")
        if not text.strip():
            doc.warnings.append("El PDF no contiene texto (¿escaneado?)")
        return doc

    text = path.read_text(encoding="utf-8", errors="replace")
    if ext in TEXT_EXTENSIONS:
        return Document(path.name, text, ext.lstrip("."))
    return Document(path.name, text, "code", {"lenguaje": CODE_LANGUAGES.get(ext, ext.lstrip("."))})
