"""Elección del proveedor del LLM por turno y por conversación (Fase 10, ADR-028)."""

import dataclasses
import json
from collections.abc import Callable

from conftest import Api, all_providers_available
from fakes import FakeLLMClient, final

from techdoc_agent import config
from techdoc_agent.core.llm import LLMUnavailableError
from techdoc_agent.core.llm_factory import provider_status

SID = "conversacion-proveedores"


def chat(api: Api, message: str, provider: str | None = None, sid: str = SID) -> dict:
    body: dict = {"session_id": sid, "message": message}
    if provider:
        body["provider"] = provider
    response = api.client.post("/api/chat", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def two_providers(make_api: Callable[..., Api], gemini_script: list) -> tuple[Api, FakeLLMClient]:
    """API cuyo proveedor por defecto (claude) es el LLM del agente y gemini es otro LLM falso."""
    gemini = FakeLLMClient(gemini_script)
    api = make_api([final("[claude] uno"), final("[claude] tres")],
                   llm_factory=lambda provider: gemini if provider == "gemini" else None)
    return api, gemini


def test_providers_endpoint_lists_both_with_model_and_availability(api: Api) -> None:
    providers = api.client.get("/api/providers").json()
    assert [p["id"] for p in providers] == ["claude", "gemini"]
    assert {"label", "model", "available", "reason", "default"} <= set(providers[0])


def test_each_turn_uses_the_requested_provider_and_says_who_answered(make_api: Callable[..., Api]) -> None:
    api, gemini = two_providers(make_api, [final("[gemini] dos")])
    first = chat(api, "pregunta uno")
    second = chat(api, "pregunta dos", provider="gemini")
    assert first["reply"] == "[claude] uno" and first["llm"]["provider"] == "claude"
    assert second["reply"] == "[gemini] dos" and second["llm"]["provider"] == "gemini"
    # Gemini recibió el historial completo: el cambio a mitad conserva el contexto
    assert [m["content"] for m in gemini.seen[0] if m["role"] == "user"] == ["pregunta uno", "pregunta dos"]


def test_without_provider_the_conversation_keeps_its_last_one(make_api: Callable[..., Api]) -> None:
    api, gemini = two_providers(make_api, [final("[gemini] dos"), final("[gemini] otra vez")])
    chat(api, "pregunta uno")
    chat(api, "pregunta dos", provider="gemini")
    third = chat(api, "pregunta tres")  # sin proveedor: sigue con gemini
    assert third["llm"]["provider"] == "gemini" and len(gemini.seen) == 2
    saved = api.client.get(f"/api/conversations/{SID}").json()
    assert saved["provider"] == "gemini"
    assert [t["llm"]["provider"] for t in saved["turns"]] == ["claude", "gemini", "gemini"]
    assert api.client.get("/api/conversations").json()[0]["provider"] == "gemini"


def test_an_unavailable_provider_is_a_409_with_the_reason(make_api: Callable[..., Api]) -> None:
    def gemini_without_key() -> list[dict[str, object]]:
        status = all_providers_available()
        status[1].update(available=False, reason="Falta GEMINI_API_KEY en backend/.env.")
        return status

    api = make_api([], provider_status=gemini_without_key)
    response = api.client.post("/api/chat", json={"session_id": SID, "message": "hola", "provider": "gemini"})
    assert response.status_code == 409
    assert "Falta GEMINI_API_KEY" in response.json()["detail"] and "Elige otro proveedor" in response.json()["detail"]
    assert api.client.get("/api/conversations").json() == []  # no se guarda nada


def test_unknown_provider_is_rejected_by_validation(api: Api) -> None:
    response = api.client.post("/api/chat", json={"session_id": SID, "message": "hola", "provider": "openai"})
    assert response.status_code == 422


def test_unavailable_error_is_a_503_with_its_message_in_json_and_sse(make_api: Callable[..., Api]) -> None:
    quota = "Se agotó la cuota diaria de Gemini. Mientras tanto, puedes elegir otro proveedor."
    api, _ = two_providers(make_api, [LLMUnavailableError(quota), LLMUnavailableError(quota)])
    response = api.client.post("/api/chat", json={"session_id": SID, "message": "hola", "provider": "gemini"})
    assert response.status_code == 503 and response.json()["detail"] == quota

    stream = api.client.post("/api/chat/stream", json={"session_id": SID, "message": "hola", "provider": "gemini"})
    errors = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")]
    assert errors[-1] == {"tipo": "error", "detalle": quota}


def test_the_real_status_never_contains_the_key(monkeypatch) -> None:
    secret = "AIzaSy-clave-secreta-de-prueba"
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, gemini_api_key=secret))
    text = json.dumps(provider_status())
    assert secret not in text and "AIza" not in text
