"""Divulgación progresiva de la skill: guías, bloque del prompt y herramienta ``cargar_guia``."""

from pathlib import Path

import pytest
from fakes import FakeLLMClient, HashingEmbedder, make_store

from techdoc_agent import config
from techdoc_agent.bootstrap import build_agent
from techdoc_agent.core.prompts import build_system_prompt
from techdoc_agent.core.skills import load_skill
from techdoc_agent.core.tools import ToolRegistry
from techdoc_agent.core.tools_skill import skill_tools

SKILL = "---\nname: demo\ndescription: Demo\n---\n\n# Demo\nMétodo base."


@pytest.fixture
def skills_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "settings", config.load_settings({"SKILLS_DIR": str(tmp_path), "ACTIVE_SKILL": "demo"}))
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "SKILL.md").write_text(SKILL, encoding="utf-8")
    return tmp_path / "demo"


def add_guide(skill_dir: Path, name: str, text: str) -> None:
    (skill_dir / "guias").mkdir(exist_ok=True)
    (skill_dir / "guias" / f"{name}.md").write_text(text, encoding="utf-8")


def test_skill_without_guides_behaves_as_before(skills_dir: Path) -> None:
    skill = load_skill()
    assert skill.guides == {} and skill_tools(skill) == []
    assert "guias_disponibles" not in build_system_prompt(skill)


def test_guides_are_loaded_with_description_and_body(skills_dir: Path) -> None:
    add_guide(skills_dir, "diagramas", "---\ndescription: Cómo hacer diagramas\n---\n\n# Guía\nPaso 1.")
    add_guide(skills_dir, "requisitos", "Sin frontmatter.")
    skill = load_skill()
    assert list(skill.guides) == ["diagramas", "requisitos"]
    assert skill.guides["diagramas"].description == "Cómo hacer diagramas" and skill.guides["diagramas"].body.endswith("Paso 1.")
    assert skill.guides["requisitos"].description == ""


def test_prompt_lists_guides_but_not_their_text(skills_dir: Path) -> None:
    add_guide(skills_dir, "diagramas", "---\ndescription: Cómo hacer diagramas\n---\n\nTEXTO-SECRETO-DE-LA-GUIA")
    prompt = build_system_prompt(load_skill())
    assert "<guias_disponibles>" in prompt and "- diagramas: Cómo hacer diagramas" in prompt
    assert "cargar_guia" in prompt and "TEXTO-SECRETO-DE-LA-GUIA" not in prompt


def test_invalid_or_empty_guides_fail_early(skills_dir: Path) -> None:
    add_guide(skills_dir, "Mala Guia", "x")
    with pytest.raises(ValueError, match="Nombre de guía no válido"):
        load_skill()
    (skills_dir / "guias" / "Mala Guia.md").unlink()
    add_guide(skills_dir, "vacia", "---\ndescription: x\n---\n")
    with pytest.raises(ValueError, match="está vacía"):
        load_skill()


def test_cargar_guia_returns_the_text_and_explains_unknown_names(skills_dir: Path) -> None:
    add_guide(skills_dir, "diagramas", "---\ndescription: d\n---\n\nPaso 1.\nPaso 2.")
    add_guide(skills_dir, "requisitos", "---\ndescription: r\n---\n\nRF-01.")
    registry = ToolRegistry(skill_tools(load_skill()))
    assert registry.dispatch("cargar_guia", {"nombre": "diagramas"}) == ("Paso 1.\nPaso 2.", False)
    assert registry.dispatch("cargar_guia", {"nombre": " requisitos "}) == ("RF-01.", False)
    text, is_error = registry.dispatch("cargar_guia", {"nombre": "../../etc/passwd"})
    assert is_error and "diagramas, requisitos" in text
    assert registry.dispatch("cargar_guia", {"nombre": 5})[1] is True
    spec = registry.specs()[0]
    assert spec.name == "cargar_guia" and spec.input_schema["properties"]["nombre"]["enum"] == ["diagramas", "requisitos"]


def test_build_agent_registers_cargar_guia_only_when_the_skill_has_guides(skills_dir: Path, tmp_path: Path) -> None:
    store = make_store("json", tmp_path / "idx")
    names = lambda: {s.name for s in build_agent(FakeLLMClient([]), store, HashingEmbedder()).tools.specs()}  # noqa: E731
    assert "cargar_guia" not in names()
    add_guide(skills_dir, "diagramas", "---\ndescription: d\n---\n\nPaso 1.")
    assert "cargar_guia" in names()


def test_the_default_skill_in_the_repository_splits_diagrams_and_requirements_into_guides() -> None:
    skill = load_skill("documentacion-tecnica")
    assert set(skill.guides) == {"diagramas", "requisitos"}
    assert "generar_diagrama" in skill.guides["diagramas"].body and "generar_requisitos" in skill.guides["requisitos"].body
    assert "generar_diagrama" not in skill.body and "RF-01" not in skill.body  # el núcleo ya no los incluye
    assert "cargar_guia" in skill.body
