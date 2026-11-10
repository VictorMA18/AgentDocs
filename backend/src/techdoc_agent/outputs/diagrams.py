"""Validación heurística (v1) y guardado de diagramas Mermaid.

El modelo escribe el código; aquí solo se comprueba y se guarda. No garantiza que
Mermaid lo renderice (eso requeriría ``mermaid-cli``, ver docs/04 y Fase 8).
"""

from __future__ import annotations

from pathlib import Path

from techdoc_agent.outputs.naming import write_unique

HEADERS: dict[str, tuple[str, ...]] = {
    "clases": ("classDiagram",),
    "secuencia": ("sequenceDiagram",),
    "flujo": ("flowchart", "graph"),
    "componentes": ("flowchart", "graph"),
    "entidad_relacion": ("erDiagram",),
    "estados": ("stateDiagram-v2", "stateDiagram"),
}
# Elemento mínimo que debe aparecer en el cuerpo para considerarlo un diagrama real.
_MIN_ELEMENT: dict[str, tuple[str, str]] = {
    "secuencia": ("->", "al menos un mensaje con flecha (A->>B: texto)"),
    "flujo": ("--", "al menos una conexión (A --> B)"),
    "componentes": ("--", "al menos una conexión (A --> B)"),
    "estados": ("-->", "al menos una transición (A --> B)"),
}
_PAIRS = {")": "(", "]": "[", "}": "{"}
MAX_CODE_CHARS = 20_000
MAX_TITLE_CHARS = 100
MAX_ERRORS = 6


def _useful_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Líneas con contenido (número 1-based), sin comentarios ``%%`` ni frontmatter ``---``."""
    out: list[tuple[int, str]] = []
    in_front = bool(lines) and lines[0].strip() == "---"
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if in_front:
            if number > 1 and line == "---":
                in_front = False
            continue
        if line and not line.startswith("%%"):
            out.append((number, line))
    return out


def _bracket_errors(tipo: str, lines: list[tuple[int, str]]) -> list[str]:
    """Paréntesis/corchetes/llaves balanceados fuera de textos entre comillas."""
    errors: list[str] = []
    stack: list[tuple[str, int]] = []
    skip_braces = tipo == "entidad_relacion"  # las relaciones ||--o{ llevan llaves sueltas
    for number, line in lines:
        if tipo in ("secuencia", "entidad_relacion") and ":" in line:
            line = line.split(":", 1)[0]  # el texto del mensaje es libre
        in_quote = False
        for char in line:
            if char == '"':
                in_quote = not in_quote
            elif in_quote or (skip_braces and char in "{}"):
                continue
            elif char in "([{":
                stack.append((char, number))
            elif char in _PAIRS:
                if stack and stack[-1][0] == _PAIRS[char]:
                    stack.pop()
                else:
                    errors.append(f"Línea {number}: '{char}' sin su apertura.")
    errors.extend(f"Línea {number}: '{char}' sin cerrar." for char, number in stack)
    return errors


def validate_mermaid(tipo: str, titulo: str, codigo: str) -> list[str]:
    """Devuelve la lista de problemas (vacía si el diagrama pasa las reglas v1)."""
    if tipo not in HEADERS:
        return [f"tipo {tipo!r} no válido. Usa uno de: {', '.join(HEADERS)}."]
    errors: list[str] = []
    if not isinstance(titulo, str) or not titulo.strip():
        errors.append("El título no puede estar vacío.")
    elif len(titulo) > MAX_TITLE_CHARS:
        errors.append(f"El título supera {MAX_TITLE_CHARS} caracteres.")
    if not isinstance(codigo, str) or not codigo.strip():
        return [*errors, "El código Mermaid está vacío."]
    if len(codigo) > MAX_CODE_CHARS:
        return [*errors, f"El código supera {MAX_CODE_CHARS} caracteres; divide el diagrama."]
    if any(line.lstrip().startswith("```") for line in codigo.splitlines()):
        errors.append("Quita los delimitadores ``` : envía solo el código Mermaid.")

    useful = _useful_lines(codigo.splitlines())
    if not useful:
        return [*errors, "El código Mermaid está vacío."]
    header = useful[0][1].split()[0]
    if header not in HEADERS[tipo]:
        esperado = " o ".join(HEADERS[tipo])
        errors.append(f"La primera línea debe empezar por {esperado} para tipo={tipo!r}; encontré {header!r}.")
    body = useful[1:]
    if not body:
        errors.append("El diagrama no tiene contenido después de la cabecera.")
    elif tipo in _MIN_ELEMENT and not any(_MIN_ELEMENT[tipo][0] in line for _, line in body):
        errors.append(f"El diagrama debe tener {_MIN_ELEMENT[tipo][1]}.")
    errors.extend(_bracket_errors(tipo, useful))
    return errors[:MAX_ERRORS]


def save_diagram(tipo: str, titulo: str, codigo: str, outputs_dir: Path) -> str:
    """Guarda el diagrama ya validado como ``diagrama-<slug>-<id>.mmd``; devuelve el nombre."""
    return write_unique(outputs_dir, "diagrama", titulo, "mmd", codigo.strip() + "\n")
