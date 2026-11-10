"""Endpoint de progreso por SSE: ``POST /api/chat/stream``."""

import json
import threading
from collections.abc import Callable

import pytest
from conftest import Api
from fakes import calls, final

from techdoc_agent.core.llm import LLMError

SID = "sesion-prueba-1"


def stream(api: Api, message: str = "hola", session_id: str = SID):
    return api.client.post("/api/chat/stream", json={"session_id": session_id, "message": message})


def parse(text: str) -> list[tuple[str, dict]]:
    """Eventos ``(tipo, datos)`` de un cuerpo SSE; ignora los comentarios (keepalive)."""
    out = []
    for block in text.split("\n\n"):
        lines = [line for line in block.splitlines() if not line.startswith(":")]
        if not lines:
            continue
        kind = lines[0].removeprefix("event: ")
        out.append((kind, json.loads(lines[1].removeprefix("data: "))))
    return out


def test_events_arrive_in_order_and_end_with_the_same_payload_as_chat(make_api: Callable[..., Api]) -> None:
    api = make_api([calls(("c1", "listar_documentos", {})), final("No hay documentos.", input_tokens=7, output_tokens=3)])
    response = stream(api, "¿qué hay?")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache" and response.headers["x-accel-buffering"] == "no"
    events = parse(response.text)
    assert [k for k, _ in events] == ["pensando", "herramienta", "pensando", "final"]
    assert events[1][1]["nombre"] == "listar_documentos" and events[1][1]["error"] is False
    final_event = events[-1][1]
    assert final_event["reply"] == "No hay documentos." and final_event["usage"] == {"input_tokens": 17, "output_tokens": 8}
    assert final_event["tool_calls"][0]["tool"] == "listar_documentos" and final_event["artifacts"] == []


def test_the_turn_is_saved_like_a_normal_chat(make_api: Callable[..., Api]) -> None:
    api = make_api([final("Hola.")])
    stream(api, "hola")
    conversation = api.client.get(f"/api/conversations/{SID}").json()
    assert conversation["turns"][0]["message"] == "hola" and conversation["turns"][0]["reply"] == "Hola."


def test_model_failure_is_a_generic_error_event_and_the_stream_still_closes(make_api: Callable[..., Api]) -> None:
    api = make_api([LLMError("detalle interno secreto")])
    events = parse(stream(api).text)
    assert [k for k, _ in events][-1] == "error"
    assert events[-1][1]["detalle"] == "El modelo no respondió correctamente. Inténtalo de nuevo."
    assert "secreto" not in json.dumps(events)


def test_invalid_request_is_rejected_before_streaming(make_api: Callable[..., Api]) -> None:
    api = make_api([final("x")])
    assert api.client.post("/api/chat/stream", json={"session_id": "corto", "message": "hola"}).status_code == 422
    assert api.client.post("/api/chat/stream", json={"session_id": SID, "message": "  "}).status_code == 422


def test_waiting_turn_announces_the_queue(make_api: Callable[..., Api]) -> None:
    api = make_api([final("Hola.")])
    core = api.client.app.state.core
    core.lock.acquire()
    result: dict = {}
    thread = threading.Thread(target=lambda: result.update(text=stream(api).text))
    thread.start()
    try:
        # el turno no puede avanzar mientras el candado esté tomado; se libera y debe completarse
        thread.join(timeout=0.5)
        assert thread.is_alive()
    finally:
        core.lock.release()
    thread.join(timeout=10)
    kinds = [k for k, _ in parse(result["text"])]
    assert kinds[0] == "en_cola" and kinds[-1] == "final"


def test_keepalive_comments_are_ignored_by_the_parser_and_sent_when_idle(monkeypatch: pytest.MonkeyPatch,
                                                                         make_api: Callable[..., Api]) -> None:
    from techdoc_agent.api import main as api_main

    monkeypatch.setattr(api_main, "STREAM_KEEPALIVE_S", 0.01)
    api = make_api([final("Hola.")])
    core = api.client.app.state.core
    core.lock.acquire()
    result: dict = {}
    thread = threading.Thread(target=lambda: result.update(text=stream(api).text))
    thread.start()
    thread.join(timeout=0.3)
    core.lock.release()
    thread.join(timeout=10)
    assert ": keepalive" in result["text"] and parse(result["text"])[-1][0] == "final"
