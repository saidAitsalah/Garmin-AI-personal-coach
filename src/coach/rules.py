"""Deterministic safety layer. The LLM proposes a session, but only inside the ceiling computed here.

Intensity scale (low -> high): rest < easy < moderate < hard.
Each rule can only LOWER the ceiling; the final ceiling is the minimum of everything that fired.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .config import Thresholds
from .metrics import DayMetrics

RANK = {"rest": 0, "easy": 1, "moderate": 2, "hard": 3}
LEVEL = {"hard": "green", "moderate": "amber", "easy": "amber", "rest": "red"}
PAIN_WORDS = re.compile(r"\b(douleur|douloureu\w*|blessure|blessé\w*|mal au|mal à|pain|injur\w*|hurt\w*)\b", re.I)


class PlanLike(Protocol):
    session_type: str
    intensity: str


@dataclass
class Readiness:
    ceiling: str = "hard"
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)          # prompt-only guidance (e.g. reduce volume)
    type_caps: dict[str, str] = field(default_factory=dict)  # per session type, e.g. {"gym": "moderate"}
    score: int | None = None                                 # simple 0-100 "forme" score

    @property
    def level(self) -> str:
        return LEVEL[self.ceiling]

    def cap(self, ceiling: str, reason: str, *, session_type: str | None = None) -> None:
        if session_type:
            current = self.type_caps.get(session_type, "hard")
            self.type_caps[session_type] = min(current, ceiling, key=RANK.__getitem__)
        else:
            self.ceiling = min(self.ceiling, ceiling, key=RANK.__getitem__)
        self.reasons.append(reason)

    def violations(self, plan: PlanLike) -> list[str]:
        """Why this plan breaks the rules (empty list = acceptable)."""
        problems = []
        stype, intensity = plan.session_type, plan.intensity
        if stype in ("rest", "recovery"):
            if stype == "recovery" and RANK[intensity] > RANK["easy"]:
                problems.append("une séance de récupération doit être d'intensité 'easy'")
            return problems
        if self.ceiling == "rest":
            problems.append("la récupération impose un jour de repos ou une récupération active (session_type rest ou recovery)")
            return problems
        limit = min(self.ceiling, self.type_caps.get(stype, "hard"), key=RANK.__getitem__)
        if RANK[intensity] > RANK[limit]:
            problems.append(f"l'intensité '{intensity}' dépasse le plafond '{limit}' pour une séance de type {stype}")
        return problems

    def for_prompt(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "intensity_ceiling": self.ceiling,
            "ceiling_per_session_type": self.type_caps,
            "reasons": self.reasons,
            "guidance": self.notes,
        }


def _fitness_score(m: DayMetrics) -> int | None:
    parts = []
    t = m.today
    if t.get("sleep_score") is not None:
        parts.append(t["sleep_score"])
    if t.get("training_readiness") is not None:
        parts.append(t["training_readiness"])
    if t.get("body_battery_wake") is not None:
        parts.append(t["body_battery_wake"])
    if t.get("hrv_overnight_avg") is not None and m.hrv_below_streak is not None:
        parts.append(max(0, 100 - 25 * m.hrv_below_streak))
    return round(sum(parts) / len(parts)) if parts else None


def assess(m: DayMetrics, t: Thresholds, journal: str = "") -> Readiness:
    r = Readiness(score=_fitness_score(m))
    today = m.today

    if not m.has_any_data:
        r.cap("moderate", "Données Garmin du jour absentes ou incomplètes : prudence par défaut.")
    elif not m.has_sleep_data:
        r.cap("moderate", "Sommeil de la nuit non synchronisé : prudence par défaut.")

    if m.hrv_below_streak >= t.hrv_streak_easy_days:
        r.cap("easy", f"HRV sous ta baseline depuis {m.hrv_below_streak} nuits d'affilée.")
    elif m.hrv_below_streak >= t.hrv_streak_moderate_days:
        r.cap("moderate", f"HRV sous ta baseline depuis {m.hrv_below_streak} nuits.")

    sleep = today.get("sleep_duration_min")
    if sleep:
        if sleep < t.very_short_sleep_min:
            r.cap("easy", f"Nuit très courte ({sleep // 60} h {sleep % 60:02d}).")
        elif sleep < t.short_sleep_min:
            r.cap("moderate", f"Nuit courte ({sleep // 60} h {sleep % 60:02d}) : pas de force lourde.")
            r.cap("moderate", "Musculation limitée à l'intensité modérée.", session_type="gym")

    ratio = today.get("load_ratio")
    if ratio is not None and ratio > t.load_ratio_high:
        r.cap("moderate", f"Ratio de charge aiguë/chronique élevé ({ratio}).")
        r.notes.append("Réduire le volume de la séance (moins de séries ou de durée).")

    if m.rhr_delta is not None and m.rhr_delta > t.rhr_delta_moderate:
        r.cap("moderate", f"Fréquence cardiaque au repos +{m.rhr_delta:.0f} bpm au-dessus de ta moyenne.")

    readiness = today.get("training_readiness")
    if readiness is not None:
        if readiness < t.readiness_rest_below:
            r.cap("rest", f"Training Readiness très bas ({readiness:.0f}).")
        elif readiness < t.readiness_easy_below:
            r.cap("easy", f"Training Readiness bas ({readiness:.0f}).")

    battery = today.get("body_battery_wake")
    if battery is not None and battery < t.body_battery_easy_below:
        r.cap("easy", f"Body Battery faible au réveil ({battery:.0f}).")

    if t.no_back_to_back_hard and any(d == 1 for d in m.days_since_hard.values() if d is not None):
        r.cap("moderate", "Séance intense hier : pas deux jours intenses de suite.")

    if journal and PAIN_WORDS.search(journal):
        r.cap("moderate", "Douleur ou blessure signalée dans ton journal.")
        r.notes.append("Éviter de solliciter la zone douloureuse décrite dans le journal.")

    return r
