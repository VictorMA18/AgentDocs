"""Cliente de Gemini con la API simulada (``httpx.MockTransport``): sin red ni clave real."""

import json

import httpx
import pytest

from techdoc_agent import config
from techdoc_agent.core.llm import ClaudeCliClient, LLMError, LLMProtocolError, LLMUnavailableError
from techdoc_agent.core.llm_factory import build_llm, llm_description
from techdoc_agent.core.llm_gemini import RESPONSE_SCHEMA, GeminiClient, parse_response
from techdoc_agent.core.tools import ToolSpec

KEY = "clave-de-prueba-123"
TOOLS = [ToolSpec("buscar_documentos", "Busca", {"type": "object", "properties": {"query": {"type": "string"}}})]


def gemini_reply(obj: object, finish: str = "STOP", usage: dict | None = None, raw: str | None = None) -> dict:
    text = raw if raw is not None else json.dumps(obj, ensure_ascii=False)
    return {
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": finish}],
        "usageMetadata": usage or {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 5},
    }


class FakeApi:
    """Responde en orden y guarda cada petición recibida."""

    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)


def ok(body: dict) -> httpx.Response:
    return httpx.Response(200, json=body)


def client(api: FakeApi, **kwargs) -> GeminiClient:
    sleeps: list[float] = []
    c = GeminiClient(model="gemini-3.6-flash", api_key=KEY, timeout_s=5, thinking_level=kwargs.pop("thinking", ""),
                     transport=httpx.MockTransport(api), sleep=sleeps.append, **kwargs)
    c.sleeps = sleeps  # type: ignore[attr-defined]
    return c


MESSAGES = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": '{"accion":"responder","texto":"¡Hola!"}'},
            {"role": "user", "content": "¿timeout?"}]


def test_request_has_the_documented_shape_and_the_key_only_in_a_header() -> None:
    api = FakeApi(ok(gemini_reply({"accion": "responder", "texto": "5 s"})))
    client(api).complete("Eres un asistente.", MESSAGES, TOOLS)
    [request] = api.requests
    assert request.method == "POST"
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
    assert request.headers["x-goog-api-key"] == KEY and KEY not in str(request.url)
    body = json.loads(request.content)
    system = body["systemInstruction"]["parts"][0]["text"]
    assert system.startswith("Eres un asistente.") and "Protocolo de respuesta" in system and "buscar_documentos" in system
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["contents"][2]["parts"] == [{"text": "¿timeout?"}]
    gen = body["generationConfig"]
    assert gen["responseMimeType"] == "application/json" and gen["responseJsonSchema"] == RESPONSE_SCHEMA
    assert "thinkingConfig" not in gen  # sin nivel configurado: el del modelo


def test_tool_args_are_declared_open_so_gemini_fills_them() -> None:
    args = RESPONSE_SCHEMA["properties"]["llamadas"]["items"]["properties"]["args"]
    assert args == {"type": "object", "additionalProperties": True}


def test_thinking_level_is_sent_in_upper_case_when_configured() -> None:
    api = FakeApi(ok(gemini_reply({"accion": "responder", "texto": "x"})))
    client(api, thinking="low").complete("s", MESSAGES[:1], [])
    assert json.loads(api.requests[0].content)["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}


def test_final_answer_and_tokens_including_thoughts() -> None:
    reply = client(FakeApi(ok(gemini_reply({"accion": "responder", "texto": "Son 5 s."})))).complete("s", MESSAGES, TOOLS)
    assert reply.text == "Son 5 s." and reply.tool_calls == []
    assert reply.input_tokens == 100 and reply.output_tokens == 25  # 20 de respuesta + 5 de razonamiento
    assert json.loads(reply.raw) == {"accion": "responder", "texto": "Son 5 s."}


def test_tool_calls_are_parsed() -> None:
    obj = {"accion": "herramientas", "llamadas": [{"id": "c1", "nombre": "buscar_documentos", "args": {"query": "timeout"}}]}
    reply = client(FakeApi(ok(gemini_reply(obj)))).complete("s", MESSAGES, TOOLS)
    assert reply.text is None and [(c.id, c.name, c.args) for c in reply.tool_calls] == [("c1", "buscar_documentos", {"query": "timeout"})]


def test_thought_parts_are_ignored() -> None:
    body = gemini_reply({"accion": "responder", "texto": "ok"})
    body["candidates"][0]["content"]["parts"].insert(0, {"text": "pienso…", "thought": True})
    assert parse_response(body).text == "ok"


def test_invalid_or_truncated_json_is_a_recoverable_protocol_error() -> None:
    with pytest.raises(LLMProtocolError, match="no es JSON"):
        parse_response(gemini_reply(None, raw="no es json"))
    with pytest.raises(LLMProtocolError, match="máximo de tokens") as exc:
        parse_response(gemini_reply(None, finish="MAX_TOKENS", raw='{"accion": "respon'))
    assert exc.value.raw == '{"accion": "respon'
    with pytest.raises(LLMProtocolError):  # JSON válido pero fuera del protocolo
        parse_response(gemini_reply({"accion": "bailar"}))


def test_blocked_prompt_or_safety_stop_are_errors() -> None:
    with pytest.raises(LLMError, match="bloqueó la petición: SAFETY"):
        parse_response({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(LLMError, match="cortó la respuesta: PROHIBITED_CONTENT"):
        parse_response(gemini_reply({"accion": "responder", "texto": "x"}, finish="PROHIBITED_CONTENT"))
    with pytest.raises(LLMError, match="ninguna respuesta"):
        parse_response({"candidates": []})


def test_overload_and_quota_are_retried_respecting_retry_after() -> None:
    api = FakeApi(httpx.Response(503, json={"error": {"code": 503, "status": "UNAVAILABLE"}}),
                  httpx.Response(429, headers={"retry-after": "7"}, json={"error": {"status": "RESOURCE_EXHAUSTED"}}),
                  ok(gemini_reply({"accion": "responder", "texto": "por fin"})))
    c = client(api)
    assert c.complete("s", MESSAGES, []).text == "por fin"
    assert len(api.requests) == 3 and c.sleeps == [2.0, 7.0]  # type: ignore[attr-defined]


def test_persistent_overload_gives_up_after_the_retries() -> None:
    api = FakeApi(*[httpx.Response(503, json={"error": {"status": "UNAVAILABLE", "message": "high demand"}})] * 4)
    with pytest.raises(LLMError, match="503. UNAVAILABLE: high demand"):
        client(api).complete("s", MESSAGES, [])
    assert len(api.requests) == 4


QUOTA_ERROR = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota", "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
     "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]}}


def test_per_minute_quota_waits_what_google_asks_and_names_the_quota() -> None:
    api = FakeApi(httpx.Response(429, json=QUOTA_ERROR), ok(gemini_reply({"accion": "responder", "texto": "ok"})))
    c = client(api)
    assert c.complete("s", MESSAGES, []).text == "ok" and c.sleeps == [37.0]  # type: ignore[attr-defined]
    api = FakeApi(*[httpx.Response(429, json={**QUOTA_ERROR})] * 4)
    with pytest.raises(LLMError, match="Cuota agotada: GenerateRequestsPerMinutePerProjectPerModel-FreeTier"):
        client(api).complete("s", MESSAGES, [])
    long_wait = {"error": {**QUOTA_ERROR["error"], "details": [{"retryDelay": "600s"}]}}
    c = client(FakeApi(httpx.Response(429, json=long_wait), ok(gemini_reply({"accion": "responder", "texto": "ok"}))))
    c.complete("s", MESSAGES, [])
    assert c.sleeps == [60.0]  # type: ignore[attr-defined]  # nunca más de un minuto por espera


def test_daily_quota_is_not_retried_and_says_so() -> None:
    daily = {"error": {**QUOTA_ERROR["error"], "details": [
        {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}, {"retryDelay": "20s"}]}}
    api = FakeApi(httpx.Response(429, json=daily))
    c = client(api)
    with pytest.raises(LLMUnavailableError, match="límite diario.*elegir otro proveedor") as exc:
        c.complete("s", MESSAGES, [])
    assert "PerDay" in str(exc.value) and len(api.requests) == 1 and c.sleeps == []  # type: ignore[attr-defined]


def test_auth_errors_are_not_retried_and_never_include_the_key() -> None:
    api = FakeApi(httpx.Response(400, json={"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "API key not valid."}}))
    with pytest.raises(LLMError) as exc:
        client(api).complete("s", MESSAGES, [])
    assert "API key not valid" in str(exc.value) and KEY not in str(exc.value) and len(api.requests) == 1
    assert not isinstance(exc.value, LLMUnavailableError)  # un 400 no es «no disponible»: mensaje genérico


def test_timeout_and_connection_errors_become_llm_errors() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento", request=request)

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(LLMError, match="tiempo máximo"):
        GeminiClient(api_key=KEY, transport=httpx.MockTransport(timeout)).complete("s", MESSAGES, [])
    with pytest.raises(LLMError, match="No se pudo conectar"):
        GeminiClient(api_key=KEY, transport=httpx.MockTransport(down)).complete("s", MESSAGES, [])


def test_missing_key_is_a_clear_error_before_any_request() -> None:
    api = FakeApi()
    with pytest.raises(LLMUnavailableError, match="Falta GEMINI_API_KEY"):
        GeminiClient(api_key="", transport=httpx.MockTransport(api)).complete("s", MESSAGES, [])
    assert api.requests == []


# --- configuración y elección del proveedor ---


def test_defaults_keep_claude_and_the_key_never_appears_in_repr() -> None:
    s = config.load_settings({"GEMINI_API_KEY": KEY})
    assert s.llm_provider == "claude" and s.gemini_model == "gemini-3.5-flash-lite" and s.gemini_thinking_level == ""
    assert s.gemini_api_key == KEY and KEY not in repr(s)


def test_invalid_provider_or_thinking_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="LLM_PROVIDER debe ser uno de"):
        config.load_settings({"LLM_PROVIDER": "openai"})
    with pytest.raises(ValueError, match="GEMINI_THINKING_LEVEL debe ser uno de"):
        config.load_settings({"GEMINI_THINKING_LEVEL": "máximo"})


def test_build_llm_picks_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", config.load_settings({}))
    assert isinstance(build_llm(), ClaudeCliClient)
    assert llm_description() == {"provider": "claude", "model": "claude-haiku-5-5"}
    monkeypatch.setattr(config, "settings", config.load_settings({"LLM_PROVIDER": "gemini", "GEMINI_MODEL": "gemini-3.8-flash"}))
    llm = build_llm()
    assert isinstance(llm, GeminiClient) and llm.model == "gemini-3.8-flash"
    assert llm_description() == {"provider": "gemini", "model": "gemini-3.8-flash"}
