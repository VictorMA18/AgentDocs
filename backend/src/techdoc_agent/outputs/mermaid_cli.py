"""Validación real de Mermaid con ``mermaid-cli`` (Fase 8, ADR-022).

``diagrams.validate_mermaid`` es heurística: no garantiza que Mermaid lo renderice. Aquí se ejecuta el
propio ``mmdc`` (Node + Chromium) sobre el código y el mensaje del parser vuelve al modelo para que se
corrija. Es opcional (``MERMAID_VALIDATE=cli``): si ``mmdc`` no existe, tarda demasiado o no puede abrir el
navegador, **no se culpa al diagrama**: se devuelve ``None`` y la herramienta sigue con la heurística.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from techdoc_agent import config
from techdoc_agent.logging_setup import log_event

# Fallos del entorno (no del diagrama): el navegador no arranca o falta algún módulo de Node.
_INFRA_MARKERS = ("Failed to launch", "Could not find Chrome", "Could not find browser", "Cannot find module",
                  "error while loading shared libraries")
MAX_ERROR_CHARS = 600
MAX_ERROR_LINES = 8
# Marcos de la traza de Node/Puppeteer/Mermaid: llevan rutas locales que no deben llegar al modelo.
_STACK_FRAME = re.compile(r"^\s*at\s|\((?:https?|file)://|node_modules|\.m?js:\d+")


def _clean_error(text: str) -> str:
    """Mensaje del parser hasta la primera línea de la traza (que lleva rutas locales), acotado."""
    lines: list[str] = []
    for line in text.splitlines():
        if _STACK_FRAME.search(line):
            break  # a partir de aquí todo es traza interna
        if not line.strip():
            continue
        lines.append(line.rstrip())
        if len(lines) >= MAX_ERROR_LINES:
            break
    return "\n".join(lines)[:MAX_ERROR_CHARS]


def validate_with_cli(codigo: str) -> list[str] | None:
    """``[]`` si Mermaid lo acepta, ``[mensaje]`` si lo rechaza, ``None`` si no se pudo comprobar."""
    settings = config.settings
    exe = settings.mermaid_cli_path
    if not exe.is_file():
        log_event(event="mermaid_cli_unavailable", reason="no existe", path=str(exe))
        return None
    with tempfile.TemporaryDirectory() as tmp:
        source, target = Path(tmp) / "diagrama.mmd", Path(tmp) / "diagrama.svg"
        source.write_text(codigo, encoding="utf-8")
        command = [str(exe), "-i", str(source), "-o", str(target), "--quiet"]
        if settings.mermaid_puppeteer_config:
            command += ["-p", settings.mermaid_puppeteer_config]
        try:  # lista de argumentos y sin shell: el código del modelo solo viaja dentro de un archivo
            proc = subprocess.run(command, capture_output=True, text=True, timeout=settings.mermaid_timeout_s,
                                  check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            log_event(event="mermaid_cli_unavailable", reason=type(exc).__name__, error=str(exc)[:200])
            return None
    if proc.returncode == 0:
        return []
    raw = (proc.stderr or "") + (proc.stdout or "")
    if any(marker in raw for marker in _INFRA_MARKERS):
        log_event(event="mermaid_cli_unavailable", reason="entorno", error=raw[:200])
        return None
    return [_clean_error(raw) or f"mmdc terminó con el código {proc.returncode}"]
