import pytest

from coach import coach_agent, llm, metrics, pipeline, report, rules
from coach.coach_agent import Block, CoachPlan
from coach.config import Thresholds

from conftest import add_history, add_metrics

T = Thresholds()
DAY = "2026-10-17"


def plan(session_type="run", intensity="easy") -> CoachPlan:
    return CoachPlan(
        session_type=session_type, intensity=intensity, duration_min=45,
        blocks=[Block(name="Footing", details="40 min zone 2 & <relax>")],
        rationale="Bonne récupération.", recovery_tip="Dors tôt.", stress_tip="Respire.",
    )


@pytest.fixture
def capped(conn):
    """A day whose ceiling is 'moderate' (short sleep)."""
    add_history(conn, DAY)
    add_metrics(conn, DAY, sleep_duration_min=330)
    m = metrics.compute(conn, DAY, T)
    return m, rules.assess(m, T)


def fake_llm(monkeypatch, *responses):
    """Make llm.generate_structured return/raise each response in turn; records the prompts."""
    calls = []
    queue = list(responses)

    def fake(system, prompt, schema):
        calls.append(prompt)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm, "generate_structured", fake)
    return calls


def test_valid_plan_is_accepted(monkeypatch, capped):
    calls = fake_llm(monkeypatch, plan("run", "moderate"))
    p, source = coach_agent.generate_plan(*capped, "", [])
    assert source == "llm" and p.session_type == "run" and len(calls) == 1


def test_rule_breaking_plan_is_retried_with_feedback(monkeypatch, capped):
    calls = fake_llm(monkeypatch, plan("run", "hard"), plan("run", "easy"))
    p, source = coach_agent.generate_plan(*capped, "", [])
    assert source == "llm" and p.intensity == "easy"
    assert "Correction requise" in calls[1] and "dépasse le plafond" in calls[1]


def test_two_violations_fall_back_to_safe_plan(monkeypatch, capped):
    fake_llm(monkeypatch, plan("gym", "hard"), plan("run", "hard"))
    p, source = coach_agent.generate_plan(*capped, "", [])
    assert source == "fallback" and not capped[1].violations(p)


def test_llm_outage_falls_back(monkeypatch, capped):
    fake_llm(monkeypatch, llm.LLMError("boom"))
    p, source = coach_agent.generate_plan(*capped, "", [])
    assert source == "fallback" and "n'a pas pu répondre" in p.rationale


def test_no_llm_flag_never_calls_the_model(monkeypatch, capped):
    calls = fake_llm(monkeypatch)
    _, source = coach_agent.generate_plan(*capped, "", [], use_llm=False)
    assert source == "fallback" and calls == []


def test_every_fallback_respects_its_own_ceiling(conn):
    add_history(conn, DAY)
    for overrides in ({}, {"sleep_duration_min": 330}, {"sleep_duration_min": 240}, {"training_readiness": 10}):
        add_metrics(conn, DAY, **overrides)
        m = metrics.compute(conn, DAY, T)
        r = rules.assess(m, T)
        assert not r.violations(coach_agent.fallback_plan(r)), r.ceiling


def test_prompt_contains_rules_data_and_knowledge(capped):
    prompt = coach_agent.build_prompt(*capped, "Fatigué", [{"date": "2026-10-16", "session_type": "gym", "intensity": "hard"}])
    assert "intensity_ceiling" in prompt and "moderate" in prompt
    assert "Fatigué" in prompt
    assert "Mes objectifs" in prompt  # knowledge/goals.md
    assert "sleep_duration_min" in prompt
    assert "2026-10-16" in prompt


def test_report_renders_and_escapes(capped):
    m, r = capped
    rep = report.render(DAY, m, r, plan("run", "moderate"), "llm")
    assert "samedi 17 octobre" in rep.html
    assert "Course / cardio modérée" in rep.html
    assert "5 h 30" in rep.plain  # sleep of 330 min
    assert "&lt;relax&gt;" in rep.html and "<relax>" in rep.plain  # escaped for Telegram, readable in console
    assert "<b>" not in rep.plain
    assert "{{" not in rep.html


def test_report_flags_fallback(capped):
    m, r = capped
    rep = report.render(DAY, m, r, coach_agent.fallback_plan(r), "fallback")
    assert "secours" in rep.plain


def test_build_report_persists_plan_only_when_asked(monkeypatch, conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY)
    fake_llm(monkeypatch, plan("gym", "moderate"), plan("gym", "moderate"))

    pipeline.build_report(conn, DAY)
    assert conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0

    pipeline.build_report(conn, DAY, persist=True)
    row = conn.execute("SELECT source, prompt_version FROM plans WHERE date = ?", (DAY,)).fetchone()
    assert row["source"] == "llm" and row["prompt_version"] == coach_agent.PROMPT_VERSION
