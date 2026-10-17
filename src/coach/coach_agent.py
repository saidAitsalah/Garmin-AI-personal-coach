"""The coach: one LLM call that picks today's session, validated against the safety rules in code."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from . import llm
from .config import KNOWLEDGE_DIR, get_settings
from .metrics import DayMetrics
from .rules import Readiness

log = logging.getLogger(__name__)

PROMPT_VERSION = "v1"
SYSTEM_PROMPT_FILE = Path(__file__).with_name("prompts") / "coach_system.md"
KNOWLEDGE_FILES = ("goals.md", "rules.md", "principles.md")
MAX_ATTEMPTS = 2


class Block(BaseModel):
    name: str
    details: str


class CoachPlan(BaseModel):
    session_type: Literal["gym", "swim", "run", "recovery", "rest"]
    intensity: Literal["easy", "moderate", "hard"]
    duration_min: int
    blocks: list[Block]
    rationale: str
    recovery_tip: str
    stress_tip: str


def load_knowledge() -> str:
    parts = []
    for name in KNOWLEDGE_FILES:
        path = KNOWLEDGE_DIR / name
        if path.exists():
            parts.append(f"<!-- {name} -->\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def system_prompt() -> str:
    return SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").replace("{language}", get_settings().language)


def build_prompt(
    metrics: DayMetrics, readiness: Readiness, journal: str, recent_plans: list[dict]
) -> str:
    def dump(obj) -> str:
        return json.dumps(obj, ensure_ascii=False, indent=1)

    previous = [
        {"date": p["date"], "session_type": p["session_type"], "intensity": p["intensity"]}
        for p in recent_plans
    ]
    return "\n\n".join([
        "# Objectifs, règles et principes\n" + load_knowledge(),
        "# Métriques du jour et tendances\n" + dump(metrics.for_prompt()),
        "# Évaluation de récupération (règles de sécurité, OBLIGATOIRES)\n" + dump(readiness.for_prompt()),
        "# Journal du jour\n" + (journal or "(rien de noté)"),
        "# Plans proposés les derniers jours (ne pas répéter)\n" + (dump(previous) if previous else "(aucun)"),
        "Propose la séance d'aujourd'hui.",
    ])


FALLBACKS: dict[str, CoachPlan] = {
    "rest": CoachPlan(
        session_type="rest", intensity="easy", duration_min=20,
        blocks=[
            Block(name="Marche douce", details="15 à 20 minutes à allure tranquille, de préférence dehors."),
            Block(name="Respiration", details="5 minutes : inspiration 4 s, expiration 6 s."),
        ],
        rationale="Plan par défaut : tes indicateurs de récupération demandent du repos aujourd'hui.",
        recovery_tip="Couche-toi 30 minutes plus tôt ce soir et évite les écrans dans l'heure qui précède.",
        stress_tip="Fais 5 minutes de respiration lente (4 s / 6 s) en milieu de journée.",
    ),
    "easy": CoachPlan(
        session_type="recovery", intensity="easy", duration_min=30,
        blocks=[
            Block(name="Marche rapide", details="20 minutes à allure facile (tu peux parler en phrases complètes)."),
            Block(name="Mobilité", details="10 minutes d'étirements doux : hanches, dos, épaules."),
        ],
        rationale="Plan par défaut : tes indicateurs recommandent une journée légère.",
        recovery_tip="Bois régulièrement et prévois un repas riche en protéines ce soir.",
        stress_tip="Prends 10 minutes de marche à la lumière du jour, sans écran.",
    ),
    "moderate": CoachPlan(
        session_type="run", intensity="easy", duration_min=40,
        blocks=[
            Block(name="Échauffement", details="5 minutes de marche rapide puis footing très lent."),
            Block(name="Footing facile", details="30 minutes en zone 2, allure où tu peux parler."),
            Block(name="Retour au calme", details="5 minutes de marche et étirements des mollets et des cuisses."),
        ],
        rationale="Plan par défaut : séance d'endurance facile, sûre quel que soit l'état de forme.",
        recovery_tip="Étire-toi 5 minutes après la séance et mange des protéines dans l'heure.",
        stress_tip="Fais quelques minutes de respiration lente avant de dormir.",
    ),
}
FALLBACKS["hard"] = FALLBACKS["moderate"]


def fallback_plan(readiness: Readiness, reason: str = "") -> CoachPlan:
    # Guidance notes (pain in the journal, high load) mean a run is not a safe blind default.
    key = "easy" if readiness.notes and readiness.ceiling in ("moderate", "hard") else readiness.ceiling
    plan = FALLBACKS[key].model_copy(deep=True)
    if reason:
        plan.rationale = f"{plan.rationale} ({reason})"
    return plan


def generate_plan(
    metrics: DayMetrics,
    readiness: Readiness,
    journal: str,
    recent_plans: list[dict],
    *,
    use_llm: bool = True,
) -> tuple[CoachPlan, str]:
    """Returns (plan, source) where source is 'llm' or 'fallback'. Never returns a rule-breaking plan."""
    if not use_llm:
        return fallback_plan(readiness, "coach IA désactivé"), "fallback"

    prompt = build_prompt(metrics, readiness, journal, recent_plans)
    system = system_prompt()
    feedback = ""
    failure = "le coach IA a proposé une séance non conforme aux règles"
    for _ in range(MAX_ATTEMPTS):
        try:
            plan = llm.generate_structured(system, prompt + feedback, CoachPlan)
        except llm.LLMError:
            log.exception("LLM unavailable")
            failure = "le coach IA n'a pas pu répondre"
            break
        problems = readiness.violations(plan)
        if not problems:
            return plan, "llm"
        log.warning("Plan rejected by rules: %s", problems)
        feedback = (
            "\n\n# Correction requise\nTa proposition précédente est refusée : "
            + " ; ".join(problems) + ". Propose une autre séance qui respecte strictement les plafonds."
        )
    return fallback_plan(readiness, failure), "fallback"
