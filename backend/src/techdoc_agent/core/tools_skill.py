"""Herramienta ``cargar_guia``: divulgación progresiva de la skill (Fase 8, ADR-021).

Solo existe si la skill activa tiene guías (``skills/<nombre>/guias/*.md``). El contenido de las guías es
instrucción del propio proyecto, no un documento del usuario: se devuelve tal cual, sin etiquetas
``<documento>``.
"""

from __future__ import annotations

from techdoc_agent.core.skills import Skill
from techdoc_agent.core.tools import Tool


def skill_tools(skill: Skill) -> list[Tool]:
    """Herramientas que expone la skill (vacío si no tiene guías)."""
    if not skill.guides:
        return []
    names = list(skill.guides)

    def cargar_guia(nombre: str) -> str:
        key = nombre.strip() if isinstance(nombre, str) else ""
        if key not in skill.guides:
            raise ValueError(f"No existe la guía {nombre!r}. Guías disponibles: {', '.join(names)}.")
        return skill.guides[key].body

    return [
        Tool(
            name="cargar_guia",
            description=(
                "Carga el texto de una guía detallada de la skill (pasos, formatos y buenas prácticas). "
                "Llámala antes de generar un diagrama o un documento de requisitos; no hace falta para "
                f"preguntas normales. Guías: {', '.join(names)}."
            ),
            input_schema={
                "type": "object",
                "properties": {"nombre": {"type": "string", "enum": names, "description": "Nombre de la guía."}},
                "required": ["nombre"],
            },
            func=cargar_guia,
        )
    ]
