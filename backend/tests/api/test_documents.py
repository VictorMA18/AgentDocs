"""Tests de subida, listado y borrado de documentos (validación de entrada no confiable)."""

import dataclasses
from pathlib import Path

import pytest
from conftest import Api

from techdoc_agent import config

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_docs" / "taskflow.md"


def upload(api: Api, name: str, content: bytes = b"# Titulo\n\nTexto de prueba sobre reintentos.\n"):
    return api.client.post("/api/documents", files={"file": (name, content, "application/octet-stream")})


def test_upload_indexes_and_lists_the_document(api: Api) -> None:
    response = upload(api, "taskflow.md", SAMPLE.read_bytes())
    body = response.json()
    assert response.status_code == 201 and body["source"] == "taskflow.md" and body["chunks"] > 3
    assert api.client.get("/api/documents").json() == [{"source": "taskflow.md", "chunks": body["chunks"]}]
    assert (api.docs_dir / "taskflow.md").is_file()
    health = api.client.get("/healthz").json()
    assert health == {"status": "ok", "documents": 1, "chunks": body["chunks"]}


def test_same_name_replaces_the_document(api: Api) -> None:
    upload(api, "nota.md", b"# A\n\nprimera version")
    upload(api, "nota.md", b"# A\n\nsegunda version")
    assert api.store.count() == 1
    assert (api.docs_dir / "nota.md").read_text() == "# A\n\nsegunda version"


@pytest.mark.parametrize("name", ["virus.exe", "script.sh", "sin_extension", "doc.md.exe"])
def test_disallowed_extension_is_415(api: Api, name: str) -> None:
    assert upload(api, name).status_code == 415
    assert api.store.count() == 0 and not list(api.docs_dir.glob("**/*"))


def test_oversized_upload_is_413_and_leaves_nothing(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, max_upload_mb=1))
    response = upload(api, "grande.md", b"x" * (1024 * 1024 + 1))
    assert response.status_code == 413 and "1 MB" in response.json()["detail"]
    assert api.store.count() == 0 and not list(api.docs_dir.glob("**/*"))


def test_content_length_is_checked_before_reading_the_body(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, max_upload_mb=1))
    response = api.client.post("/api/documents", content=b"x", headers={
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
    assert [p.name for p in api.docs_dir.iterdir()] == [expected]
    assert not (api.root / "evil.md").exists() and not (api.docs_dir.parent / "evil.md").exists()


@pytest.mark.parametrize("name", [".env", "...", "", "   "])
def test_unusable_names_are_rejected(api: Api, name: str) -> None:
    assert upload(api, name).status_code in (400, 415, 422)
    assert api.store.count() == 0


def test_empty_file_is_400(api: Api) -> None:
    assert upload(api, "vacio.md", b"").status_code == 400


def test_document_without_indexable_text_is_400_and_leaves_nothing(api: Api) -> None:
    response = upload(api, "blanco.md", b"   \n\n  \n")
    assert response.status_code == 400 and api.store.count() == 0
    assert not list(api.docs_dir.glob("**/*"))


def test_missing_file_field_is_422(api: Api) -> None:
    assert api.client.post("/api/documents").status_code == 422


def test_delete_removes_index_entries_and_original(api: Api) -> None:
    upload(api, "nota.md")
    response = api.client.delete("/api/documents/nota.md")
    assert response.status_code == 200 and response.json()["chunks_removed"] == 1
    assert api.store.count() == 0 and not (api.docs_dir / "nota.md").exists()
    assert api.client.delete("/api/documents/nota.md").status_code == 404


@pytest.mark.parametrize("source", [".env", "a%2f..%2fb.md", "x" * 101])
def test_delete_rejects_odd_names(api: Api, source: str) -> None:
    assert api.client.delete(f"/api/documents/{source}").status_code in (400, 404)
