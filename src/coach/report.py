"""Render the morning report (Telegram-flavoured HTML) from metrics, readiness and plan."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .coach_agent import CoachPlan
from .config import TEMPLATES_DIR
from .metrics import DayMetrics
from .rules import Readiness

DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]
LEVELS = {"green": ("🟢", "bonne"), "amber": ("🟠", "moyenne"), "red": ("🔴", "faible")}
SESSION_TITLES = {
    "gym": "Musculation", "swim": "Natation", "run": "Course / cardio",
    "recovery": "Récupération active", "rest": "Repos",
}
INTENSITY_FR = {"easy": "facile", "moderate": "modérée", "hard": "intense"}

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True,
    undefined=StrictUndefined, trim_blocks=False, keep_trailing_newline=False,
)


@dataclass
class Report:
    html: str
    plain: str
    plan: CoachPlan
    readiness: Readiness
    source: str


def _fmt_duration(minutes: float | None) -> str | None:
    if minutes is None:
        return None
    return f"{int(minutes) // 60} h {int(minutes) % 60:02d}"


def _trend(today: float | None, avg: float | None) -> str:
    if today is None or avg is None or avg == 0:
        return ""
    change = (today - avg) / abs(avg)
    return "▲" if change > 0.03 else "▼" if change < -0.03 else "►"


def _metric_rows(m: DayMetrics) -> list[dict[str, Any]]:
    t = m.today
    spec = [
        ("Sommeil", "sleep_duration_min", _fmt_duration, "{}"),
        ("Score de sommeil", "sleep_score", None, "{:.0f}"),
        ("HRV (nuit)", "hrv_overnight_avg", None, "{:.0f} ms"),
        ("FC au repos", "rhr", None, "{:.0f} bpm"),
        ("Stress moyen", "avg_stress", None, "{:.0f}"),
        ("Body Battery au réveil", "body_battery_wake", None, "{:.0f}"),
    ]
    rows = []
    for label, key, fmt, pattern in spec:
        value = t.get(key)
        if value is None:
            continue
        avg = m.avg7.get(key)
        shown = fmt(value) if fmt else pattern.format(value)
        shown_avg = (fmt(avg) if fmt else pattern.format(avg)) if avg is not None else ""
        rows.append({"label": label, "value": shown, "trend": _trend(value, avg), "avg7": shown_avg})
    if t.get("hrv_status"):
        rows.append({"label": "Statut HRV", "value": str(t["hrv_status"]).lower(), "trend": "", "avg7": ""})
    return rows


def _date_fr(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{DAYS_FR[d.weekday()]} {d.day} {MONTHS_FR[d.month - 1]}"


def render(day: str, m: DayMetrics, readiness: Readiness, plan: CoachPlan, source: str) -> Report:
    emoji, label = LEVELS[readiness.level]
    title = SESSION_TITLES[plan.session_type]
    if plan.session_type not in ("rest", "recovery"):
        title += f" {INTENSITY_FR[plan.intensity]}"
    notes = []
    if not m.has_sleep_data:
        notes.append("Données de sommeil indisponibles à l'envoi : recommandations prudentes.")
    if source == "fallback":
        notes.append("Programme de secours : le coach IA n'a pas été utilisé pour ce rapport.")

    context = {
        "date_fr": _date_fr(day),
        "level_emoji": emoji,
        "level_label": label,
        "score": readiness.score,
        "reasons": readiness.reasons,
        "metrics": _metric_rows(m),
        "sleep_debt": _fmt_duration(m.sleep_debt_7d_min) if m.sleep_debt_7d_min >= 30 else None,
        "plan": {
            "title": title, "duration_min": plan.duration_min, "blocks": plan.blocks,
            "rationale": plan.rationale, "recovery_tip": plan.recovery_tip, "stress_tip": plan.stress_tip,
        },
        "notes": notes,
    }
    body = re.sub(r"\n{3,}", "\n\n", _env.get_template("morning.html.j2").render(**context)).strip()
    return Report(html=body, plain=to_plain(body), plan=plan, readiness=readiness, source=source)


def to_plain(telegram_html: str) -> str:
    return html.unescape(re.sub(r"</?(b|i)>", "", telegram_html))
