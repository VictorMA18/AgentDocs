"""Resume turnos antiguos para recortar la memoria sin perder el hilo.

El resumen guarda *de qué se habló y qué quería el usuario*, nunca datos
técnicos: esos se vuelven a buscar en el RAG (los resultados de herramientas
ni siquiera se muestran al resumidor).
"""

from __future__ import annotations

import json
import re

from techdoc_agent.core.llm import LLMClient, LLMError, Message

MAX_MESSAGE_CHARS = 1500  # tope por mensaje en la transcripción a resumir

SUMMARIZER_SYSTEM = """\
Eres un resumidor de conversaciones para un asistente de documentación técnica.
Recibes un resumen previo (puede estar vacío) y una transcripción de turnos antiguos.
Escribe un resumen NUEVO y acumulativo, en el idioma del usuario, de máximo ~1200 caracteres, con:
- Los temas tratados y lo que el usuario quería lograr.
- Los nombres de los documentos consultados.
- Preferencias o decisiones del usuario (formato, idioma, nivel de detalle).
- Preguntas que quedaron sin respuesta.
NO incluyas valores, parámetros, versiones, código ni afirmaciones técnicas: esos datos deben volver a buscarse en los documentos.
Responde solo con el resumen, usando la acción "responder"."""

_RESULT = re.compile(
    r'<resultado_herramienta id="([^"]*)" error="(true|false)">(.*?)</resultado_herramienta>', re.DOTALL
)
_SOURCE = re.compile(r'fuente="([^"]+)"')


def _cut(text: str) -> str:
    return text if len(text) <= MAX_MESSAGE_CHARS else text[:MAX_MESSAGE_CHARS] + "…"


def _render_results(content: str) -> str:
    """Resultados de herramientas → una línea con tamaño y fuentes, sin contenido."""
    def line(m: re.Match[str]) -> str:
        fuentes = ", ".join(dict.fromkeys(_SOURCE.findall(m.group(3)))) or "sin fuentes"
        estado = "error" if m.group(2) == "true" else "ok"
        return f"[resultado {estado}: {len(m.group(3))} caracteres; fuentes: {fuentes}]"
    return _RESULT.sub(line, content)


def _render_assistant(content: str) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return _cut(content)
    if data.get("accion") == "responder":
        return _cut(str(data.get("texto", "")))
    nombres = ", ".join(str(c.get("nombre")) for c in data.get("llamadas", []))
    return f"[usó herramientas: {nombres}]"


def render_transcript(messages: list[Message]) -> str:
    bloques = []
    for m in messages:
        if m["role"] == "assistant":
            bloques.append(f"[asistente] {_render_assistant(m['content'])}")
        elif m["content"].startswith("<resultado_herramienta"):
            bloques.append(f"[sistema] {_render_results(m['content'])}")
        else:
            bloques.append(f"[usuario] {_cut(m['content'])}")
    return "\n".join(bloques)


def summarize(llm: LLMClient, previous: str, messages: list[Message]) -> str:
    """Una llamada al LLM (sin herramientas) que devuelve el resumen acumulado."""
    prompt = (
        f"<resumen_previo>\n{previous or '(vacío)'}\n</resumen_previo>\n\n"
        f"<transcripcion>\n{render_transcript(messages)}\n</transcripcion>\n\n"
        "Escribe el resumen nuevo."
    )
    reply = llm.complete(SUMMARIZER_SYSTEM, [{"role": "user", "content": prompt}], [])
    text = (reply.text or "").strip()
    if not text:
        raise LLMError("El resumidor devolvió un resumen vacío")
    return text
