"""Cabeceras de seguridad, API pura (sin páginas) y frontera de arquitectura."""

import dataclasses
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import Api

import techdoc_agent
from techdoc_agent import config

SRC = Path(techdoc_agent.__file__).parent


def test_security_headers_on_every_response(api: Api) -> None:
    for path in ("/", "/healthz", "/api/documents", "/api/artifacts/../x", "/no-existe"):
        headers = api.client.get(path).headers
        assert headers["content-security-policy"].startswith("default-src 'none'"), path
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"


def test_no_cors_headers(api: Api) -> None:
    response = api.client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert not any(h.lower().startswith("access-control-") for h in response.headers)


def test_api_docs_endpoints_are_disabled(api: Api) -> None:
    assert all(api.client.get(p).status_code == 404 for p in ("/docs", "/redoc", "/openapi.json"))


def test_backend_serves_no_pages() -> None:
    """Fase 9.B (ADR-026): la interfaz es el frontend Next.js; el backend no sirve HTML ni estáticos."""
    assert not (SRC / "api" / "static").exists()


def test_root_and_static_paths_are_not_found(api: Api) -> None:
    for path in ("/", "/static/app.js", "/index.html"):
        response = api.client.get(path)
        assert response.status_code == 404 and "text/html" not in response.headers["content-type"], path


def test_core_and_rag_do_not_import_the_api() -> None:
    """RNF-07: el núcleo no depende de los adaptadores."""
    for package in ("core", "rag", "outputs"):
        for file in (SRC / package).rglob("*.py"):
            text = file.read_text(encoding="utf-8")
            assert "techdoc_agent.api" not in text and "mcp_server" not in text, file


def test_api_only_touches_the_core_through_its_public_entry_points() -> None:
    """Revisa todos los archivos de la API (main, app, routers…); los imports entre ellos no cuentan."""
    imports = {
        module
        for file in (SRC / "api").rglob("*.py")
        for module in re.findall(r"^\s*from (techdoc_agent[\w.]*) import", file.read_text(encoding="utf-8"), flags=re.M)
        if not module.startswith("techdoc_agent.api")
    }
    assert imports <= {
        "techdoc_agent", "techdoc_agent.core.agent", "techdoc_agent.core.llm", "techdoc_agent.rag.embeddings",
        "techdoc_agent.rag.ingest", "techdoc_agent.rag.store", "techdoc_agent.bootstrap",
        "techdoc_agent.rag.factory", "techdoc_agent.core.memory", "techdoc_agent.core.transcripts",
        "techdoc_agent.logging_setup", "techdoc_agent.outputs.artifacts", "techdoc_agent.core.llm_factory"}, imports


# --- CORS (ADR-025): solo los orígenes del frontend configurados ---

FRONT = "http://localhost:3000"


def test_configured_frontend_origin_gets_cors_headers(api: Api) -> None:
    response = api.client.get("/healthz", headers={"Origin": FRONT})
    assert response.headers["access-control-allow-origin"] == FRONT
    assert "default-src 'none'" in response.headers["content-security-policy"]  # el guard sigue actuando


def test_preflight_allows_the_methods_the_frontend_uses(api: Api) -> None:
    response = api.client.options("/api/documents/x.md", headers={
        "Origin": FRONT, "Access-Control-Request-Method": "DELETE", "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200 and response.headers["access-control-allow-origin"] == FRONT
    assert "DELETE" in response.headers["access-control-allow-methods"]
    put = api.client.options("/api/documents", headers={"Origin": FRONT, "Access-Control-Request-Method": "PUT"})
    assert put.status_code == 400  # método no permitido


def test_early_413_is_readable_by_the_frontend(api: Api) -> None:
    """CORS va por fuera del guard: el rechazo por Content-Length también lleva su cabecera."""
    huge = str(config.settings.max_upload_mb * 1024 * 1024 * 2)
    response = api.client.post("/api/documents", headers={"Origin": FRONT, "Content-Length": huge,
                                                           "Content-Type": "multipart/form-data; boundary=x"}, content=b"")
    assert response.status_code == 413 and response.headers["access-control-allow-origin"] == FRONT


def test_empty_cors_origins_disables_cors(make_api: Callable[..., Api], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, cors_origins=()))
    response = make_api().client.get("/healthz", headers={"Origin": FRONT})
    assert not any(h.lower().startswith("access-control-") for h in response.headers)


def test_cors_origins_default_and_parsing() -> None:
    assert config.load_settings({}).cors_origins == ("http://localhost:3000", "http://127.0.0.1:3000")
    assert config.load_settings({"CORS_ORIGINS": " https://a.example , "}).cors_origins == ("https://a.example",)
    assert config.load_settings({"CORS_ORIGINS": ""}).cors_origins == config.load_settings({}).cors_origins  # vacía = por defecto
