"""Cabeceras de seguridad, estáticos y frontera de arquitectura."""

import re
from pathlib import Path

from conftest import Api

import techdoc_agent
from techdoc_agent.api.main import STATIC_DIR

SRC = Path(techdoc_agent.__file__).parent


def test_security_headers_on_every_response(api: Api) -> None:
    for path in ("/", "/healthz", "/api/documents", "/api/artifacts/../x", "/no-existe"):
        headers = api.client.get(path).headers
        assert "default-src 'self'" in headers["content-security-policy"], path
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"


def test_no_cors_headers(api: Api) -> None:
    response = api.client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert not any(h.lower().startswith("access-control-") for h in response.headers)


def test_api_docs_endpoints_are_disabled(api: Api) -> None:
    assert all(api.client.get(p).status_code == 404 for p in ("/docs", "/redoc", "/openapi.json"))


def test_index_and_static_files_are_served(api: Api) -> None:
    index = api.client.get("/")
    assert index.status_code == 200 and "text/html" in index.headers["content-type"]
    assert api.client.get("/static/app.js").status_code == 200
    assert api.client.get("/static/app.css").status_code == 200
    assert api.client.get("/static/../main.py").status_code in (400, 404)


def test_page_has_no_inline_scripts_or_handlers() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.S)
    assert scripts and all(not body.strip() for body in scripts)  # todos con src, ninguno con código
    assert not re.search(r"\son[a-z]+\s*=", html)  # onclick=, onload=…


def test_external_scripts_are_pinned_and_have_integrity() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<script\b[^>]*\bsrc=\"https://[^>]*>", html):
        assert re.search(r"@\d+\.\d+\.\d+", tag), tag  # versión fija
        assert "integrity=\"sha384-" in tag and "crossorigin" in tag, tag


def test_core_and_rag_do_not_import_the_api() -> None:
    """RNF-07: el núcleo no depende de los adaptadores."""
    for package in ("core", "rag", "outputs"):
        for file in (SRC / package).rglob("*.py"):
            text = file.read_text(encoding="utf-8")
            assert "techdoc_agent.api" not in text and "mcp_server" not in text, file


def test_api_only_touches_the_core_through_its_public_entry_points() -> None:
    text = (SRC / "api" / "main.py").read_text(encoding="utf-8")
    imports = set(re.findall(r"^\s*from (techdoc_agent[\w.]*) import", text, flags=re.M))
    assert imports <= {
        "techdoc_agent", "techdoc_agent.core.agent", "techdoc_agent.core.llm", "techdoc_agent.rag.embeddings",
        "techdoc_agent.rag.ingest", "techdoc_agent.rag.store", "techdoc_agent.bootstrap",
        "techdoc_agent.rag.factory", "techdoc_agent.core.memory", "techdoc_agent.core.transcripts",
        "techdoc_agent.logging_setup"}, imports
