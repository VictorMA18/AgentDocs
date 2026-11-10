"""Qué archivos guardaron las herramientas de salida durante un turno.

Lo comparten los adaptadores (la API lo devuelve en ``artifacts``) y las evaluaciones. El nombre
sale del texto que devolvió la herramienta (``Diagrama válido y guardado como X.``); solo cuenta
si es de un tipo conocido y el archivo existe de verdad en la carpeta de salidas.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

ARTIFACT_TYPES = {".mmd": "mermaid", ".md": "requirements"}
OUTPUT_TOOLS = ("generar_diagrama", "generar_requisitos")
_NAME_IN_RESULT = re.compile(r"guardad[oa]s? como ([a-z0-9][a-z0-9._-]*\.(?:mmd|md))")


class _Trace(Protocol):
    """Lo que se necesita de una herramienta ejecutada (``core.agent.ToolTrace`` lo cumple)."""

    name: str
    args: dict[str, Any]
    is_error: bool
    result: str


def turn_artifacts(traces: Iterable[_Trace], outputs_dir: Path) -> list[dict[str, str]]:
    """Artefactos guardados por ``generar_diagrama``/``generar_requisitos``: nombre, tipo y título."""
    found = []
    for trace in traces:
        match = _NAME_IN_RESULT.search(trace.result)
        if trace.name not in OUTPUT_TOOLS or trace.is_error or not match:
            continue
        path = outputs_dir / match.group(1)
        if path.is_file():
            found.append({"name": path.name, "type": ARTIFACT_TYPES[path.suffix],
                          "title": str(trace.args.get("titulo", ""))})
    return found
