"""Documentos de cada conversación (ADR-032): subir, listar, quitar y leer un fragmento citado, con la
validación de entrada no confiable de siempre y el aislamiento entre conversaciones."""

import dataclasses
from pathlib import Path

import pytest
from conftest import Api
from fakes import calls, final

from techdoc_agent import config

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_docs" / "taskflow.md"
CID = "conversacion-1"
OTHER = "conversacion-2"


def docs_url(cid: str = CID) -> str:
    return f"/api/conversations/{cid}/documents"


def upload(api: Api, name: str, content: bytes = b"# Titulo\n\nTexto de prueba sobre reintentos.\n", cid: str = CID):
    return api.client.post(docs_url(cid), files={"file": (name, content, "application/octet-stream")})


def docs_dir(api: Api, cid: str = CID) -> Path:
    return api.root / "data" / "chats" / cid / "documents"


def chunks(api: Api, cid: str = CID) -> int:
    return sum(d["chunks"] for d in api.client.get(docs_url(cid)).json())


def test_upload_indexes_and_lists_the_document_of_that_conversation(api: Api) -> None:
    response = upload(api, "taskflow.md", SAMPLE.read_bytes())
    body = response.json()
    assert response.status_code == 201 and body["source"] == "taskflow.md" and body["chunks"] > 3
    assert api.client.get(docs_url()).json() == [{"source": "taskflow.md", "chunks": body["chunks"]}]
    assert (docs_dir(api) / "taskflow.md").is_file()
    assert api.store.count() == 0  # el índice global (consola, MCP, evaluaciones) no se toca
    assert api.client.get(docs_url(OTHER)).json() == []  # otra conversación no lo ve
    assert not (api.root / "data" / "chats" / OTHER).exists()  # y listar no crea nada en disco


def test_first_upload_creates_the_conversation(api: Api) -> None:
    upload(api, "nota.md")
    listing = api.client.get("/api/conversations").json()
    assert [(c["id"], c["title"], c["turns"]) for c in listing] == [(CID, "nota.md", 0)]  # el primer documento le da nombre
    upload(api, "otra.md")
    assert api.client.get("/api/conversations").json()[0]["title"] == "nota.md"  # el segundo no lo cambia


def test_same_name_replaces_the_document(api: Api) -> None:
    upload(api, "nota.md", b"# A\n\nprimera version")
    upload(api, "nota.md", b"# A\n\nsegunda version")
    assert chunks(api) == 1
    assert (docs_dir(api) / "nota.md").read_text() == "# A\n\nsegunda version"


@pytest.mark.parametrize("name", ["virus.exe", "script.sh", "sin_extension", "doc.md.exe"])
def test_disallowed_extension_is_415(api: Api, name: str) -> None:
    assert upload(api, name).status_code == 415
    assert chunks(api) == 0 and not docs_dir(api).exists()


def test_oversized_upload_is_413_and_leaves_nothing(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, max_upload_mb=1))
    response = upload(api, "grande.md", b"x" * (1024 * 1024 + 1))
    assert response.status_code == 413 and "1 MB" in response.json()["detail"]
    assert chunks(api) == 0 and not docs_dir(api).exists()


def test_content_length_is_checked_before_reading_the_body(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, max_upload_mb=1))
    response = api.client.post(docs_url(), content=b"x", headers={
        "content-length": str(50 * 1024 * 1024), "content-type": "multipart/form-data; boundary=x"})
    assert response.status_code == 413


@pytest.mark.parametrize("name,expected", [
    ("../../evil.md", "evil.md"),
    ("..\\..\\evil.md", "evil.md"),
    ("/etc/passwd.md", "passwd.md"),
    ("a/b/c.md", "c.md"),
    ("mi archivo (1).md", "mi-archivo-1-.md"),
    ("ñandú.md", "and-.md"),
])
def test_filenames_are_sanitized_and_stay_inside_the_documents_dir(api: Api, name: str, expected: str) -> None:
    response = upload(api, name)
    assert response.status_code == 201 and response.json()["source"] == expected
    assert [p.name for p in docs_dir(api).iterdir()] == [expected]
    assert not (api.root / "evil.md").exists() and not (docs_dir(api).parent / "evil.md").exists()


@pytest.mark.parametrize("name", [".env", "...", "", "   "])
def test_unusable_names_are_rejected(api: Api, name: str) -> None:
    assert upload(api, name).status_code in (400, 415, 422)
    assert chunks(api) == 0


@pytest.mark.parametrize("cid", ["corto", "con espacio!!", "x" * 65, "..", "a.b.c.d.e"])
def test_malformed_conversation_ids_are_400_and_touch_nothing(api: Api, cid: str) -> None:
    assert upload(api, "nota.md", cid=cid).status_code in (400, 404)
    assert api.client.get(docs_url(cid)).status_code in (400, 404)
    assert not (api.root / "data" / "chats").exists()


def test_empty_file_is_400(api: Api) -> None:
    assert upload(api, "vacio.md", b"").status_code == 400


def test_document_without_indexable_text_is_400_and_leaves_nothing(api: Api) -> None:
    response = upload(api, "blanco.md", b"   \n\n  \n")
    assert response.status_code == 400 and chunks(api) == 0
    assert not list(docs_dir(api).glob("**/*"))


def test_missing_file_field_is_422(api: Api) -> None:
    assert api.client.post(docs_url()).status_code == 422


def test_delete_removes_index_entries_and_original(api: Api) -> None:
    upload(api, "nota.md")
    response = api.client.delete(f"{docs_url()}/nota.md")
    assert response.status_code == 200 and response.json()["chunks_removed"] == 1
    assert chunks(api) == 0 and not (docs_dir(api) / "nota.md").exists()
    assert api.client.delete(f"{docs_url()}/nota.md").status_code == 404
    assert api.client.delete(f"{docs_url(OTHER)}/nota.md").status_code == 404


@pytest.mark.parametrize("source", [".env", "a%2f..%2fb.md", "x" * 101])
def test_delete_rejects_odd_names(api: Api, source: str) -> None:
    assert api.client.delete(f"{docs_url()}/{source}").status_code in (400, 404)


def test_fragment_returns_the_cited_text_only_from_that_conversation(api: Api) -> None:
    upload(api, "taskflow.md", SAMPLE.read_bytes())
    fragment = api.client.get(f"/api/conversations/{CID}/fragments/taskflow.md%230").json()
    assert fragment["id"] == "taskflow.md#0" and fragment["source"] == "taskflow.md" and fragment["text"]
    assert api.client.get(f"/api/conversations/{OTHER}/fragments/taskflow.md%230").status_code == 404
    assert api.client.get(f"/api/conversations/{CID}/fragments/taskflow.md%23999").status_code == 404


@pytest.mark.parametrize("chunk_id", ["taskflow.md", "%23", "..%2f.env%230", ".env%230", "a.md%23-1", "a.md%23x"])
def test_fragment_rejects_odd_ids(api: Api, chunk_id: str) -> None:
    assert api.client.get(f"/api/conversations/{CID}/fragments/{chunk_id}").status_code in (400, 404)


def test_deleting_the_conversation_deletes_its_documents(make_api) -> None:  # noqa: ANN001
    api = make_api([final("ok")])
    upload(api, "nota.md")
    assert api.client.delete(f"/api/conversations/{CID}").status_code == 200
    assert not (api.root / "data" / "chats" / CID).exists()
    assert api.client.get(docs_url()).json() == []


def test_the_agent_only_searches_the_documents_of_the_conversation(make_api) -> None:  # noqa: ANN001
    api = make_api([
        calls(("c1", "listar_documentos", {})), final("Tengo nota.md."),
        calls(("c2", "listar_documentos", {})), final("No hay documentos."),
    ])
    upload(api, "nota.md")
    api.client.post("/api/chat", json={"session_id": CID, "message": "¿qué documentos hay?"})
    api.client.post("/api/chat", json={"session_id": OTHER, "message": "¿qué documentos hay?"})
    results = [m["content"] for m in api.llm.seen[-1] if "<resultado_herramienta" in str(m["content"])]
    first = [str(m["content"]) for m in api.llm.seen[1] if "<resultado_herramienta" in str(m["content"])]
    assert "nota.md" in first[-1]  # la conversación con el documento lo ve
    assert "nota.md" not in results[-1]  # la otra no
