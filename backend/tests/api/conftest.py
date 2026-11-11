"""Cliente de pruebas de la API: núcleo real con LLM y embedder falsos, todo en carpetas temporales."""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from fakes import FakeLLMClient, HashingEmbedder
from fastapi.testclient import TestClient

from techdoc_agent import config
from techdoc_agent.api.main import create_app
from techdoc_agent.bootstrap import build_agent
from techdoc_agent.core.llm import LLMReply
from techdoc_agent.core.memory import Memory
from techdoc_agent.rag.store_json import JsonVectorStore


@dataclass
class Api:
    client: TestClient
    llm: FakeLLMClient
    store: JsonVectorStore
    root: Path

    @property
    def docs_dir(self) -> Path:
        return self.root / "data" / "documents"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def conversations_dir(self) -> Path:
        return self.root / "data" / "conversations"


def all_providers_available() -> list[dict[str, object]]:
    """Estado fijo de los proveedores: no depende de si hay clave de Gemini o CLI de Claude."""
    return [{"id": p, "label": p.title(), "model": f"{p}-modelo", "available": True, "reason": None,
             "default": p == config.settings.llm_provider} for p in ("claude", "gemini")]


@pytest.fixture
def make_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Api]:
    settings = dataclasses.replace(
        config.settings, data_dir=tmp_path / "data", outputs_dir=tmp_path / "outputs",
        logs_dir=tmp_path / "logs", llm_provider="claude")  # fijo: no depende del .env de quien ejecuta
    monkeypatch.setattr(config, "settings", settings)

    def make(script: list[LLMReply | Exception] | None = None, *,
             llm_factory: Callable[[str], object] | None = None,
             provider_status: Callable[[], list[dict[str, object]]] = all_providers_available) -> Api:
        llm = FakeLLMClient(script or [])
        store, embedder = JsonVectorStore(tmp_path / "idx"), HashingEmbedder()
        memory = Memory(settings.data_dir / "conversations")
        app = create_app(build_agent(llm, store, embedder, memory), store, embedder,
                         llm_factory=llm_factory, provider_status=provider_status)  # type: ignore[arg-type]
        return Api(TestClient(app), llm, store, tmp_path)

    return make


@pytest.fixture
def api(make_api: Callable[..., Api]) -> Api:
    return make_api()
