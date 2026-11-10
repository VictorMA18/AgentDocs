"""Carga de skills: un directorio ``skills/<nombre>/SKILL.md`` con método y formato.

La skill dice *cómo* trabajar; el conocimiento vive en los documentos indexados.

Divulgación progresiva (Fase 8): una skill puede traer ``guias/<nombre>.md``. El system prompt solo
lista sus nombres y descripciones; el agente carga el texto de una guía con la herramienta
``cargar_guia`` cuando la necesita. Sin carpeta ``guias/`` la skill se comporta como siempre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from techdoc_agent import config

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass(frozen=True)
class Guide:
    name: str
    description: str
    body: str


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str  # contenido sin el frontmatter
    guides: dict[str, Guide] = field(default_factory=dict)  # se cargan bajo demanda con ``cargar_guia``


def _parse(text: str) -> tuple[dict[str, str], str]:
    """Separa el frontmatter (pares ``clave: valor`` simples) del cuerpo."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta, text[match.end():].strip()


def _load_guides(directory: Path) -> dict[str, Guide]:
    """Lee ``guias/*.md`` (nombre = archivo sin extensión, en minúsculas); falla pronto si alguna es inválida."""
    guides: dict[str, Guide] = {}
    if not directory.is_dir():
        return guides
    for path in sorted(directory.glob("*.md")):
        if not _SLUG.match(path.stem):
            raise ValueError(f"Nombre de guía no válido: {path.name!r}")
        meta, body = _parse(path.read_text(encoding="utf-8"))
        if not body:
            raise ValueError(f"La guía {path.stem!r} está vacía")
        guides[path.stem] = Guide(path.stem, meta.get("description", ""), body)
    return guides


def load_skill(name: str | None = None) -> Skill:
    """Lee ``<SKILLS_DIR>/<name>/SKILL.md``. ``name`` por defecto: ``ACTIVE_SKILL``."""
    name = name or config.settings.active_skill
    if not _SLUG.match(name):  # impide rutas como ``../x``
        raise ValueError(f"Nombre de skill no válido: {name!r}")
    path = config.settings.skills_dir / name / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(f"No existe la skill {name!r} (se buscó {path})")
    meta, body = _parse(path.read_text(encoding="utf-8"))
    if not body:
        raise ValueError(f"La skill {name!r} está vacía")
    return Skill(name=meta.get("name", name), description=meta.get("description", ""), body=body,
                 guides=_load_guides(path.parent / "guias"))
