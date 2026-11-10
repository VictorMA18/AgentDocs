"""Tests del endpoint de chat."""

import dataclasses
from collections.abc import Callable

import pytest
from conftest import Api
from fakes import calls, final

from techdoc_agent import config
from techdoc_agent.core.llm import LLMError

SID = "sesion-prueba-1"
DIAGRAM = {"tipo": "flujo", "titulo": "Cola de trabajos", "codigo": "flowchart TD\n    A[Encolar] --> B[Procesar]"}


def post(api: Api, message: str = "hola", session_id: str = SID):
    return api.client.post("/api/chat", json={"session_id": session_id, "message": message})


def test_simple_turn_has_the_documented_shape(make_api: Callable[..., Api]) -> None:
    api = make_api([final("¡Hola!", input_tokens=7, output_tokens=3)])
    body = post(api).json()
    assert body == {"reply": "¡Hola!", "tool_calls": [], "artifacts": [],
                    "usage": {"input_tokens": 7, "output_tokens": 3}, "truncated": False}


def test_tool_calls_are_listed(make_api: Callable[..., Api]) -> None:
    api = make_api([calls(("c1", "listar_documentos", {})), final("No hay documentos.")])
    body = post(api, "¿qué hay indexado?").json()
    [call] = body["tool_calls"]
    assert call["tool"] == "listar_documentos" and call["args"] == {} and call["is_error"] is False
    assert isinstance(call["duration_ms"], int)


def test_generated_diagram_is_reported_as_artifact(make_api: Callable[..., Api]) -> None:
    api = make_api([calls(("c1", "generar_diagrama", DIAGRAM)), final("Guardado.")])
    [artifact] = post(api, "haz un diagrama").json()["artifacts"]
    assert artifact["type"] == "mermaid" and artifact["title"] == "Cola de trabajos"
    assert artifact["name"].startswith("diagrama-") and artifact["name"].endswith(".mmd")
    downloaded = api.client.get(f"/api/artifacts/{artifact['name']}")
    assert downloaded.status_code == 200 and "flowchart TD" in downloaded.text


def test_rejected_diagram_is_not_an_artifact(make_api: Callable[..., Api]) -> None:
    bad = {**DIAGRAM, "codigo": "flowchart TD\n    A[Encolar --> B"}
    api = make_api([calls(("c1", "generar_diagrama", bad)), final("No pude.")])
    body = post(api).json()
    assert body["tool_calls"][0]["is_error"] is True and body["artifacts"] == []


def test_session_memory_is_kept_between_requests(make_api: Callable[..., Api]) -> None:
    api = make_api([final("uno"), final("dos")])
    post(api, "primera")
    post(api, "segunda")
    assert [m["content"] for m in api.llm.seen[1]][0] == "primera"  # la 2.ª llamada ve la 1.ª


@pytest.mark.parametrize("payload", [
    {"session_id": "corto", "message": "hola"},                 # id demasiado corto
    {"session_id": "con espacios!!", "message": "hola"},        # caracteres no permitidos
    {"session_id": SID, "message": ""},
    {"session_id": SID, "message": "   "},                      # solo espacios
    {"session_id": SID, "message": "x" * 8001},                 # demasiado largo
    {"session_id": SID},
    {},
])
def test_invalid_requests_are_422(api: Api, payload: dict) -> None:
    assert api.client.post("/api/chat", json=payload).status_code == 422
    assert api.llm.seen == []  # ni siquiera se llamó al modelo


def test_llm_failure_is_a_generic_502(make_api: Callable[..., Api]) -> None:
    api = make_api([LLMError("claude falló en /home/usuario/secreto: traza interna")])
    response = post(api)
    assert response.status_code == 502
    assert "secreto" not in response.text and "traza" not in response.text


def test_truncated_flag(make_api: Callable[..., Api], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, max_agent_iterations=1))
    api = make_api([calls(("c1", "listar_documentos", {}))])
    body = post(api).json()
    assert body["truncated"] is True
