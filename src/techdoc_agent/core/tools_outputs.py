"""Herramientas ``generar_diagrama`` y ``generar_requisitos``.

No generan contenido con IA: validan lo que escribe el modelo y, si hay errores,
los devuelven (``is_error``) para que se corrija. Los archivos se guardan en
``outputs/`` con nombre generado por el sistema; al modelo solo se le devuelve el nombre.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from techdoc_agent import config
from techdoc_agent.core.tools import Tool
from techdoc_agent.outputs.diagrams import HEADERS, save_diagram, validate_mermaid
from techdoc_agent.outputs.mermaid_cli import validate_with_cli
from techdoc_agent.outputs.requirements_doc import save_requirements, validate_requirements

RETRY_HINT = "Corrige estos problemas y vuelve a llamar a la herramienta."


def _fail(errors: list[str]) -> ValueError:
    return ValueError("\n".join(f"- {e}" for e in errors) + f"\n{RETRY_HINT}")


def output_tools(outputs_dir: Path | None = None) -> list[Tool]:
    """Crea las herramientas de salida; ``outputs_dir`` por defecto es ``OUTPUTS_DIR``."""

    def target() -> Path:
        return outputs_dir or config.settings.outputs_dir

    def generar_diagrama(tipo: str, titulo: str, codigo: str) -> str:
        errors = validate_mermaid(tipo, titulo, codigo)
        if errors:
            raise _fail(errors)
        if config.settings.mermaid_validate == "cli":  # tras la heurística (barata); si mmdc no está, se sigue sin él
            rejected = validate_with_cli(codigo)
            if rejected:
                raise _fail([f"Mermaid rechazó el diagrama: {message}" for message in rejected])
        name = save_diagram(tipo, titulo, codigo, target())
        return f"Diagrama válido y guardado como {name}."

    def generar_requisitos(
        titulo: str, funcionales: list[dict[str, Any]], no_funcionales: list[dict[str, Any]] | None = None
    ) -> str:
        errors, warnings = validate_requirements(titulo, funcionales, no_funcionales)
        if errors:
            raise _fail(errors)
        name = save_requirements(titulo, funcionales, no_funcionales, target())
        text = f"Requisitos guardados como {name} ({len(funcionales)} funcionales, {len(no_funcionales or [])} no funcionales)."
        if warnings:
            text += "\nAdvertencias:\n" + "\n".join(f"- {w}" for w in warnings)
        return text

    return [
        Tool(
            name="generar_diagrama",
            description=(
                "Valida y guarda un diagrama escrito en Mermaid. Tú escribes el código Mermaid; "
                "la herramienta comprueba la sintaxis y lo guarda. Si devuelve errores, "
                "corrígelos y vuelve a llamarla. Basa el diagrama en información recuperada "
                "de los documentos, no en suposiciones."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": list(HEADERS)},
                    "titulo": {"type": "string"},
                    "codigo": {"type": "string", "description": "Código Mermaid completo, sin delimitadores ```."},
                },
                "required": ["tipo", "titulo", "codigo"],
            },
            func=generar_diagrama,
        ),
        Tool(
            name="generar_requisitos",
            description=(
                "Crea un documento de requisitos estructurado (funcionales y no funcionales) y "
                "lo guarda en Markdown. Cada requisito debe tener id único, descripción "
                "verificable, prioridad MoSCoW y criterio de aceptación. Devuelve advertencias "
                "si falta información."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "funcionales": {"type": "array", "items": {"type": "object", "properties": {
                        "id": {"type": "string", "pattern": "^RF-\\d{2,3}$"},
                        "descripcion": {"type": "string"},
                        "prioridad": {"type": "string", "enum": ["M", "S", "C", "W"]},
                        "criterio_aceptacion": {"type": "string"},
                        "fuente": {"type": "string", "description": "Documento y fragmento de donde se deduce, si aplica."},
                    }, "required": ["id", "descripcion", "prioridad", "criterio_aceptacion"]}},
                    "no_funcionales": {"type": "array", "items": {"type": "object", "properties": {
                        "id": {"type": "string", "pattern": "^RNF-\\d{2,3}$"},
                        "categoria": {"type": "string"},
                        "descripcion": {"type": "string"},
                        "metrica": {"type": "string"},
                    }, "required": ["id", "categoria", "descripcion", "metrica"]}},
                },
                "required": ["titulo", "funcionales"],
            },
            func=generar_requisitos,
        ),
    ]
