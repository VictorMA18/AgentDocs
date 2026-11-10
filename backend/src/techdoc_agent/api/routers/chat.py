"""Chat: un turno completo (``/api/chat``) o el mismo turno con progreso en vivo por SSE (``/api/chat/stream``)."""

from __future__ import annotations

import json
import queue
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from techdoc_agent import config
from techdoc_agent.api.deps import Core, get_core
from techdoc_agent.api.schemas import ChatRequest
from techdoc_agent.core.llm import LLMError
from techdoc_agent.logging_setup import log_event
from techdoc_agent.outputs.artifacts import turn_artifacts

STREAM_KEEPALIVE_S = 15

router = APIRouter()


def run_turn(core: Core, body: ChatRequest, on_event: Any = None) -> dict[str, Any]:
    """Un turno de chat completo bajo el candado: agente, respuesta documentada y transcripción."""
    with core.lock:
        try:
            result = core.agent.run(body.session_id, body.message, on_event=on_event)
        except LLMError:  # el detalle ya está en el log; al cliente, un mensaje genérico
            raise HTTPException(502, "El modelo no respondió correctamente. Inténtalo de nuevo.") from None
        response = {
            "reply": result.text,
            "tool_calls": [
                {"tool": t.name, "args": t.args, "is_error": t.is_error, "duration_ms": t.duration_ms}
                for t in result.tool_calls
            ],
            "artifacts": turn_artifacts(result.tool_calls, config.settings.outputs_dir),
            "usage": {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
            "truncated": result.truncated,
        }
        try:
            core.transcripts.append(body.session_id, {"message": body.message, **response})
        except OSError as exc:  # la respuesta ya existe: no se pierde por un fallo de disco
            log_event(session=body.session_id, event="transcript_save_error", error=str(exc))
    return response


def sse(event: dict[str, Any]) -> str:
    """Un evento SSE: ``event:`` con el tipo y ``data:`` con el JSON (una sola línea)."""
    return f"event: {event['tipo']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/api/chat")
def chat(body: ChatRequest, core: Core = Depends(get_core)) -> dict[str, Any]:
    return run_turn(core, body)


@router.post("/api/chat/stream")
def chat_stream(body: ChatRequest, core: Core = Depends(get_core)) -> StreamingResponse:
    """Mismo turno que ``/api/chat`` pero en SSE: eventos de progreso y, al final, ``final`` o ``error``.

    Es progreso, no tokens: la respuesta del modelo llega entera dentro de un JSON estructurado.
    El turno corre en un hilo; si el cliente se desconecta, termina y se guarda igualmente.
    """
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def work() -> None:
        try:
            if core.lock.locked():  # otro turno en curso: se avisa en vez de dejar al cliente a oscuras
                events.put({"tipo": "en_cola"})
            events.put({"tipo": "final", **run_turn(core, body, on_event=events.put)})
        except HTTPException as exc:
            events.put({"tipo": "error", "detalle": exc.detail})
        except Exception as exc:  # noqa: BLE001 - nada de trazas al cliente
            log_event(session=body.session_id, event="stream_error", error=str(exc))
            events.put({"tipo": "error", "detalle": "Error interno del servidor."})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def generate() -> Any:
        while True:
            try:
                event = events.get(timeout=STREAM_KEEPALIVE_S)
            except queue.Empty:
                yield ": keepalive\n\n"  # un comentario SSE: evita que un proxy cierre la conexión inactiva
                continue
            if event is None:
                return
            yield sse(event)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
