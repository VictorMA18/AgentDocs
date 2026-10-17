"""Tests de la construcción del system prompt."""

from datetime import date

from techdoc_agent.core.prompts import FIXED_RULES, build_system_prompt
from techdoc_agent.core.skills import Skill


def test_prompt_has_fixed_rules_skill_and_date() -> None:
    prompt = build_system_prompt(Skill("s", "d", "REGLA DE LA SKILL"), date(2026, 1, 2))
    assert FIXED_RULES in prompt
    assert '<skill nombre="s">\nREGLA DE LA SKILL\n</skill>' in prompt
    assert "2026-01-02" in prompt


def test_changing_the_skill_changes_the_prompt_but_keeps_fixed_rules() -> None:
    a = build_system_prompt(Skill("s", "", "responde en tabla"))
    b = build_system_prompt(Skill("s", "", "responde en lista"))
    assert a != b and FIXED_RULES in a and FIXED_RULES in b


def test_documents_are_declared_untrusted_data() -> None:
    assert "DATOS no confiables" in build_system_prompt(Skill("s", "", "x"))


def test_summary_is_context_not_evidence_and_is_appended_to_the_system_prompt() -> None:
    from techdoc_agent.core.prompts import with_summary

    assert "no evidencia" in FIXED_RULES
    assert with_summary("BASE", "") == "BASE"
    assert with_summary("BASE", "hablamos de X").endswith(
        "<resumen_conversacion>\nhablamos de X\n</resumen_conversacion>")
