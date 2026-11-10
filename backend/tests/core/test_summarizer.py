"""Tests del resumidor de turnos antiguos (con LLM falso)."""

import json

import pytest
from fakes import FakeLLMClient, final

from techdoc_agent.core.llm import LLMError
from techdoc_agent.core.summarizer import render_transcript, summarize

HERRAMIENTAS = json.dumps({"accion": "herramientas", "llamadas": [
    {"id": "c1", "nombre": "buscar_documentos", "args": {"query": "q"}}]})
RESULTADO = (
    '<resultado_herramienta id="c1" error="false">'
    '<documento fuente="taskflow.md#4" seccion="W" score="0.8">concurrency=4 SECRETO</documento>\n\n'
    '<documento fuente="taskflow.md#5" seccion="R" score="0.7">max_retries=3</documento>'
    "</resultado_herramienta>"
)
MESSAGES = [
    {"role": "user", "content": "¿concurrencia?"},
    {"role": "assistant", "content": HERRAMIENTAS},
    {"role": "user", "content": RESULTADO},
    {"role": "assistant", "content": json.dumps({"accion": "responder", "texto": "Es 4."})},
]


def test_transcript_hides_tool_results_but_keeps_sources_and_size() -> None:
    text = render_transcript(MESSAGES)
    assert "SECRETO" not in text and "max_retries" not in text
    assert "fuentes: taskflow.md#4, taskflow.md#5" in text
    assert "[usó herramientas: buscar_documentos]" in text
    assert "[usuario] ¿concurrencia?" in text and "[asistente] Es 4." in text


def test_long_messages_are_cut() -> None:
    text = render_transcript([{"role": "user", "content": "a" * 5000}])
    assert len(text) < 1700 and text.endswith("…")


def test_summarize_calls_llm_without_tools_and_includes_previous_summary() -> None:
    llm = FakeLLMClient([final("  nuevo resumen  ")])
    assert summarize(llm, "resumen viejo", MESSAGES) == "nuevo resumen"
    prompt = llm.seen[0][0]["content"]
    assert "resumen viejo" in prompt and "¿concurrencia?" in prompt


def test_empty_summary_is_an_error() -> None:
    with pytest.raises(LLMError):
        summarize(FakeLLMClient([final("   ")]), "", MESSAGES)
