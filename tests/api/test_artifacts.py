"""Tests de listado y descarga de artefactos (el nombre llega de la red: no es confiable)."""

import os
from pathlib import Path

import pytest
from conftest import Api

SECRET = "SECRETO-NO-DEBE-SALIR"


@pytest.fixture
def populated(api: Api) -> Api:
    api.outputs_dir.mkdir(parents=True)
    (api.outputs_dir / "diagrama-flujo-cola-3f2a.mmd").write_text("flowchart TD\n  A --> B", encoding="utf-8")
    (api.outputs_dir / "requisitos-reintentos-9c1d.md").write_text("# Requisitos", encoding="utf-8")
    (api.outputs_dir / "notas.txt").write_text("no es un artefacto", encoding="utf-8")
    (api.root / ".env").write_text(f"CLAVE={SECRET}", encoding="utf-8")
    (api.root / "secreto.md").write_text(SECRET, encoding="utf-8")
    return api


def test_list_shows_only_valid_artifacts(populated: Api) -> None:
    body = populated.client.get("/api/artifacts").json()
    assert {a["name"]: a["type"] for a in body} == {
        "diagrama-flujo-cola-3f2a.mmd": "mermaid", "requisitos-reintentos-9c1d.md": "requirements"}
    assert all({"size", "modified"} <= a.keys() for a in body)


def test_list_is_empty_without_outputs_dir(api: Api) -> None:
    assert api.client.get("/api/artifacts").json() == []


def test_download_returns_the_file_as_an_attachment(populated: Api) -> None:
    response = populated.client.get("/api/artifacts/diagrama-flujo-cola-3f2a.mmd")
    assert response.status_code == 200 and response.text == "flowchart TD\n  A --> B"
    assert response.headers["content-type"].startswith("text/plain")
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.parametrize("path", [
    "../../.env", "..%2f..%2f.env", "%2e%2e/%2e%2e/.env", "..%5c..%5c.env", "....//....//.env",
    "/etc/passwd", "%2fetc%2fpasswd", ".env", "..", "%2e%2e", "secreto.md", "../secreto.md",
    "..%2fsecreto.md", "DIAGRAMA-FLUJO-COLA-3F2A.MMD", "notas.txt", "a..b.md", "nada.mmd",
])
def test_traversal_and_odd_names_never_return_content(populated: Api, path: str) -> None:
    response = populated.client.get(f"/api/artifacts/{path}")
    assert response.status_code in (400, 404, 405)
    assert SECRET not in response.text


def test_symlink_pointing_outside_is_rejected(populated: Api) -> None:
    link = populated.outputs_dir / "enlace-3f2a.md"
    os.symlink(populated.root / "secreto.md", link)
    response = populated.client.get("/api/artifacts/enlace-3f2a.md")
    assert response.status_code == 404 and SECRET not in response.text


def test_directory_named_like_an_artifact_is_not_served(populated: Api) -> None:
    (populated.outputs_dir / "carpeta.md").mkdir()
    assert populated.client.get("/api/artifacts/carpeta.md").status_code == 404
