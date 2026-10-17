"""Tests de la carga de skills."""

from pathlib import Path

import pytest

from techdoc_agent import config
from techdoc_agent.core.skills import load_skill


@pytest.fixture
def skills_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        config, "settings", config.load_settings({"SKILLS_DIR": str(tmp_path)})
    )
    return tmp_path


def write_skill(root: Path, name: str, text: str) -> None:
    (root / name).mkdir()
    (root / name / "SKILL.md").write_text(text, encoding="utf-8")


def test_loads_real_skill_without_frontmatter() -> None:
    skill = load_skill()
    assert skill.name == "documentacion-tecnica"
    assert skill.description.startswith("Responde preguntas")
    assert skill.body.startswith("# Skill") and "---" not in skill.body.splitlines()[0]


def test_parses_frontmatter_and_body(skills_dir: Path) -> None:
    write_skill(skills_dir, "mia", "---\nname: mia\ndescription: hace cosas\n---\n\n# Hola\ncuerpo\n")
    skill = load_skill("mia")
    assert (skill.name, skill.description, skill.body) == ("mia", "hace cosas", "# Hola\ncuerpo")


def test_skill_without_frontmatter_uses_directory_name(skills_dir: Path) -> None:
    write_skill(skills_dir, "simple", "solo texto")
    assert load_skill("simple").name == "simple"


def test_missing_skill(skills_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match="nada"):
        load_skill("nada")


@pytest.mark.parametrize("name", ["../x", "a/b", "", ".oculta", "A B"])
def test_invalid_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        load_skill(name or "/")


def test_empty_skill(skills_dir: Path) -> None:
    write_skill(skills_dir, "vacia", "---\nname: vacia\n---\n")
    with pytest.raises(ValueError, match="vacía"):
        load_skill("vacia")
