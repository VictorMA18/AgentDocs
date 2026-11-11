"""``LLMClient`` sobre la API REST de Gemini (proveedor alternativo, ADR-024).

Usa el mismo protocolo JSON que el cliente de Claude (``accion``/``llamadas``/``texto``), así el
bucle, las herramientas y la skill no cambian. La API recibe el historial como ``contents`` (rol
``user`` o ``model``) y el system prompt en ``systemInstruction``; la salida JSON se fuerza con
``responseMimeType`` + ``responseJsonSchema``.

La clave viaja en la cabecera ``x-goog-api-key`` (no en la URL): así no aparece en los logs ni en
los mensajes de error. Nunca se registra.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

import httpx

from techdoc_agent import config
from techdoc_agent.core.llm import (
    OUTPUT_SCHEMA,
    LLMError,
    LLMProtocolError,
    LLMReply,
    LLMUnavailableError,
    Message,
    build_system_text,
    reply_from_structured,
)
from techdoc_agent.core.tools import ToolSpec

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUS = (429, 500, 503)  # cuota agotada o servidor saturado: suele pasar en segundos
MAX_RETRIES = 3
MAX_RETRY_WAIT_S = 60  # el plan gratuito limita peticiones por minuto: a veces hay que esperar casi un minuto
ROLES = {"user": "user", "assistant": "model"}
BLOCKING_FINISH = ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION")


def _gemini_schema() -> dict[str, Any]:
    """El schema del protocolo con ``args`` abierto.

    Con ``{"type": "object"}`` a secas Gemini obliga a que ``args`` salga vacío (medido): hay que
    declarar ``additionalProperties: true`` para que rellene los argumentos de cada herramienta.
    """
    schema = copy.deepcopy(OUTPUT_SCHEMA)
    schema["properties"]["llamadas"]["items"]["properties"]["args"] = {"type": "object", "additionalProperties": True}
    return schema


RESPONSE_SCHEMA = _gemini_schema()


class GeminiClient:
    """Llama a ``models/{modelo}:generateContent``. ``transport`` permite simular la API en los tests."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout_s: int | None = None,
        thinking_level: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        s = config.settings
        self.model = model or s.gemini_model
        self._api_key = api_key if api_key is not None else s.gemini_api_key
        self.timeout_s = timeout_s or s.llm_timeout_s
        self.thinking_level = s.gemini_thinking_level if thinking_level is None else thinking_level
        self._transport = transport
        self._sleep = sleep

    def _body(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> dict[str, Any]:
        generation: dict[str, Any] = {"responseMimeType": "application/json", "responseJsonSchema": RESPONSE_SCHEMA}
        if self.thinking_level:
            generation["thinkingConfig"] = {"thinkingLevel": self.thinking_level.upper()}
        return {
            "systemInstruction": {"parts": [{"text": build_system_text(system, tools)}]},
            "contents": [{"role": ROLES[m["role"]], "parts": [{"text": m["content"]}]} for m in messages],
            "generationConfig": generation,
        }

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        """POST con reintentos ante 429/500/503 (respeta ``Retry-After`` si viene).

        La cuota diaria agotada no se reintenta: no vuelve hasta el día siguiente.
        """
        url = API_URL.format(model=self.model)
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout_s, transport=self._transport) as client:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    response = client.post(url, headers=headers, json=body)
                except httpx.TimeoutException:
                    raise LLMError(f"Gemini superó el tiempo máximo ({self.timeout_s} s).") from None
                except httpx.HTTPError as exc:
                    raise LLMError(f"No se pudo conectar con la API de Gemini: {type(exc).__name__}.") from None
                if response.status_code not in RETRY_STATUS or attempt == MAX_RETRIES or _daily_quota(response):
                    return response
                self._sleep(self._retry_wait(response, attempt))
        raise AssertionError("inalcanzable")

    @staticmethod
    def _retry_wait(response: httpx.Response, attempt: int) -> float:
        """Lo que pide Google (``RetryInfo.retryDelay`` o ``Retry-After``); si no dice nada, 2, 4, 8 s."""
        wait = _retry_delay(response)
        if wait is None:
            header = response.headers.get("retry-after", "")
            wait = float(header) if header.replace(".", "", 1).isdigit() else 2.0 * 2**attempt
        return min(wait, MAX_RETRY_WAIT_S)

    @staticmethod
    def _api_error(response: httpx.Response) -> str:
        """Mensaje de error de la API (el cuerpo de Google, nunca la petición ni la clave)."""
        try:
            error = response.json().get("error", {})
            detail = f"{error.get('status', '')}: {error.get('message', '')}".strip(": ")[:300]
        except (ValueError, AttributeError):
            detail = response.text[:300]
        quotas = _quota_ids(response)
        if quotas:
            detail += f" Cuota agotada: {', '.join(quotas)}."
        if _daily_quota(response):
            detail += " Es el límite diario: vuelve a estar disponible al día siguiente."
        return f"La API de Gemini respondió {response.status_code}. {detail}"

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        if not self._api_key:
            raise LLMUnavailableError(
                "Falta GEMINI_API_KEY: ponla en backend/.env para usar Gemini, o elige otro proveedor.")
        response = self._post(self._body(system, messages, tools))
        if response.status_code != 200:
            message = self._api_error(response)
            if response.status_code == 429:  # cuota (diaria o por minuto tras los reintentos): se puede mostrar
                raise LLMUnavailableError(f"{message} Mientras tanto, puedes elegir otro proveedor.")
            raise LLMError(message)
        return parse_response(response.json())


def _quota_ids(response: httpx.Response) -> list[str]:
    """Identificadores de cuota (``QuotaFailure.violations[].quotaId``) del cuerpo del error."""
    try:
        details = response.json().get("error", {}).get("details", [])
        return [v["quotaId"] for d in details for v in d.get("violations", []) if v.get("quotaId")]
    except (ValueError, AttributeError, TypeError):
        return []


def _daily_quota(response: httpx.Response) -> bool:
    """``True`` si se agotó una cuota diaria (``...PerDay...``): reintentar no sirve."""
    return response.status_code == 429 and any("PerDay" in q for q in _quota_ids(response))


def _retry_delay(response: httpx.Response) -> float | None:
    """Segundos de ``RetryInfo.retryDelay`` (p. ej. ``"37s"``) en el cuerpo del error, si los hay."""
    try:
        details = response.json().get("error", {}).get("details", [])
    except (ValueError, AttributeError):
        return None
    for detail in details:
        delay = str(detail.get("retryDelay", ""))
        if delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


def parse_response(data: dict[str, Any]) -> LLMReply:
    """Convierte la respuesta de ``generateContent`` en un ``LLMReply`` validado."""
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise LLMError(f"Gemini bloqueó la petición: {feedback['blockReason']}.")
    candidates = data.get("candidates") or []
    if not candidates:
        raise LLMError("Gemini no devolvió ninguna respuesta.")
    candidate = candidates[0]
    finish = candidate.get("finishReason", "")
    if finish in BLOCKING_FINISH:
        raise LLMError(f"Gemini cortó la respuesta: {finish}.")
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    try:
        structured = json.loads(text)
    except json.JSONDecodeError:
        # Recuperable: el bucle se lo devuelve al modelo para que responda con el protocolo.
        motivo = " (se alcanzó el máximo de tokens)" if finish == "MAX_TOKENS" else ""
        raise LLMProtocolError(f"La salida de Gemini no es JSON válido{motivo}.", text) from None
    usage = data.get("usageMetadata") or {}
    output = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    return reply_from_structured(structured, usage.get("promptTokenCount", 0), output)
