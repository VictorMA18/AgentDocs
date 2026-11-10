"""Conversaciones guardadas: transcripción, memoria del agente y reinicio del servidor."""

from collections.abc import Callable

import pytest
from conftest import Api
from fakes import calls, final

from techdoc_agent.core.llm import LLMError

SID = "conversacion-1"


def chat(api: Api, message: str, session_id: str = SID):
    return api.client.post("/api/chat", json={"session_id": session_id, "message": message})


def test_a_chat_turn_is_saved_with_everything_the_page_shows(make_api: Callable[..., Api]) -> None:
    api = make_api([calls(("c1", "listar_documentos", {})), final("No hay documentos.")])
    reply = chat(api, "¿qué hay indexado?").json()
    saved = api.client.get(f"/api/conversations/{SID}").json()
    assert saved["id"] == SID and saved["title"] == "¿qué hay indexado?"
    [turn] = saved["turns"]
    assert {k: turn[k] for k in reply} == reply  # exactamente lo que devolvió /api/chat
    assert turn["message"] == "¿qué hay indexado?" and "ts" in turn


def test_list_shows_newest_first_and_without_turns(make_api: Callable[..., Api]) -> None:
    api = make_api([final("a"), final("b"), final("c")])
    chat(api, "primera conversación", "conversacion-a")
    chat(api, "segunda conversación", "conversacion-b")
    chat(api, "más sobre la segunda", "conversacion-b")
    listing = api.client.get("/api/conversations").json()
    assert [(c["id"], c["turns"]) for c in listing] == [("conversacion-b", 2), ("conversacion-a", 1)]
    assert set(listing[0]) == {"id", "title", "updated", "turns"}


def test_failed_chat_creates_no_conversation(make_api: Callable[..., Api]) -> None:
    api = make_api([LLMError("se cayó")])
    assert chat(api, "hola").status_code == 502
    assert api.client.get("/api/conversations").json() == []
    assert not api.conversations_dir.exists() or not list(api.conversations_dir.glob("*"))


def test_invalid_chat_creates_no_conversation(api: Api) -> None:
    assert chat(api, "").status_code == 422
    assert api.client.get("/api/conversations").json() == []


def test_server_restart_keeps_the_list_and_the_agent_context(make_api: Callable[..., Api]) -> None:
    first = make_api([final("Me llamo Claude.")])
    chat(first, "¿cómo te llamas?")

    restarted = make_api([final("Te dije que Claude.")])  # nueva app, mismas carpetas
    assert [c["id"] for c in restarted.client.get("/api/conversations").json()] == [SID]
    assert restarted.client.get(f"/api/conversations/{SID}").json()["turns"][0]["reply"] == "Me llamo Claude."
    chat(restarted, "¿y cómo era?")
    assert restarted.llm.seen[0][0] == {"role": "user", "content": "¿cómo te llamas?"}  # contexto previo
    assert len(restarted.client.get(f"/api/conversations/{SID}").json()["turns"]) == 2


def test_delete_removes_transcript_memory_and_files(make_api: Callable[..., Api]) -> None:
    api = make_api([final("uno"), final("dos")])
    chat(api, "hola")
    assert sorted(p.name for p in api.conversations_dir.iterdir()) == [
        f"{SID}.memory.json", f"{SID}.turns.json"]
    assert api.client.delete(f"/api/conversations/{SID}").json() == {"id": SID}
    assert list(api.conversations_dir.iterdir()) == []
    assert api.client.get(f"/api/conversations/{SID}").status_code == 404
    assert api.client.delete(f"/api/conversations/{SID}").status_code == 404
    chat(api, "de nuevo")  # empieza sin contexto
    assert api.llm.seen[1] == [{"role": "user", "content": "de nuevo"}]


def test_unknown_conversation_is_404(api: Api) -> None:
    assert api.client.get("/api/conversations/no-existe-1").status_code == 404


@pytest.mark.parametrize("conversation_id", ["corto", "con espacio!!", "x" * 65, ".env", "a.b.c.d.e.f.g.h"])
def test_malformed_ids_are_400(api: Api, conversation_id: str) -> None:
    assert api.client.get(f"/api/conversations/{conversation_id}").status_code == 400
    assert api.client.delete(f"/api/conversations/{conversation_id}").status_code == 400


@pytest.mark.parametrize("path", ["../../.env", "..%2f..%2f.env", "%2e%2e/%2e%2e/.env", "..%5c..%5cx", "/etc/passwd"])
def test_traversal_ids_never_touch_other_files(api: Api, path: str) -> None:
    secret = api.root / "secreto.turns.json"
    secret.write_text("{}", encoding="utf-8")
    assert api.client.get(f"/api/conversations/{path}").status_code in (400, 404)
    assert api.client.delete(f"/api/conversations/{path}").status_code in (400, 404, 405)
    assert secret.exists() and (api.root / ".env").exists() is False


def test_conversations_are_independent(make_api: Callable[..., Api]) -> None:
    api = make_api([final("uno"), final("dos")])
    chat(api, "mensaje de A", "conversacion-a")
    chat(api, "mensaje de B", "conversacion-b")
    assert api.llm.seen[1] == [{"role": "user", "content": "mensaje de B"}]  # B no ve a A
