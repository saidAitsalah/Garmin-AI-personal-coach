"""Trends, baselines and load indicators computed from the normalised tables (no LLM, no network).

Convention: "avg7" and "avg30" are means over the 7 / 30 days BEFORE the report day, so that today's
value is compared against a baseline that does not include itself.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .config import Thresholds

TRACKED = ("sleep_score", "sleep_duration_min", "hrv_overnight_avg", "rhr", "avg_stress", "body_battery_wake")
SESSION_TYPES = ("gym", "swim", "run")


@dataclass
class DayMetrics:
    date: str
    today: dict[str, Any]
    avg7: dict[str, float | None]
    avg30: dict[str, float | None]
    hrv_below_streak: int
    sleep_debt_7d_min: int
    rhr_delta: float | None
    days_since_hard: dict[str, int | None]
    recent_activities: list[dict[str, Any]]
    week_counts: dict[str, int]
    has_sleep_data: bool = False
    has_any_data: bool = False
    missing: list[str] = field(default_factory=list)

    def for_prompt(self) -> dict[str, Any]:
        """Compact, identity-free view sent to the LLM."""
        keep = {k: v for k, v in self.today.items() if v is not None and k != "date"}
        return {
            "date": self.date,
            "today": keep,
            "avg_previous_7_days": {k: v for k, v in self.avg7.items() if v is not None},
            "avg_previous_30_days": {k: v for k, v in self.avg30.items() if v is not None},
            "hrv_days_below_baseline_in_a_row": self.hrv_below_streak,
            "sleep_debt_last_7_days_min": self.sleep_debt_7d_min,
            "resting_hr_vs_30d_mean": self.rhr_delta,
            "days_since_last_hard_session": self.days_since_hard,
            "sessions_last_7_days": self.week_counts,
            "recent_activities": self.recent_activities,
        }


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _rows(conn: sqlite3.Connection, start: date, end: date) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
        (start.isoformat(), end.isoformat()),
    )
    return [dict(r) for r in cur]


def _window_avg(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    return {k: _mean([r[k] for r in rows if r.get(k) is not None]) for k in TRACKED}


def _hrv_below(row: dict[str, Any]) -> bool | None:
    """True/False when the night's HRV can be judged against the baseline, None when unknown."""
    avg, low = row.get("hrv_overnight_avg"), row.get("hrv_baseline_low")
    if avg is not None and low is not None:
        return avg < low
    if row.get("hrv_status"):
        return str(row["hrv_status"]).upper() in {"LOW", "POOR"}
    return None


def _hrv_streak(rows_desc: list[dict[str, Any]]) -> int:
    streak = 0
    for row in rows_desc:
        below = _hrv_below(row)
        if below is None:
            continue  # no HRV that night: neither extends nor breaks the streak
        if not below:
            break
        streak += 1
    return streak


def is_hard(activity: dict[str, Any], t: Thresholds) -> bool:
    return (activity.get("aerobic_te") or 0) >= t.hard_aerobic_te or (
        activity.get("anaerobic_te") or 0) >= t.hard_anaerobic_te


def compute(conn: sqlite3.Connection, day: str, t: Thresholds) -> DayMetrics:
    d = date.fromisoformat(day)
    today_rows = _rows(conn, d, d)
    today = today_rows[0] if today_rows else {}

    prev30 = _rows(conn, d - timedelta(days=30), d - timedelta(days=1))
    prev7 = [r for r in prev30 if r["date"] >= (d - timedelta(days=7)).isoformat()]

    last14_desc = list(reversed(_rows(conn, d - timedelta(days=13), d)))
    last7 = [r for r in _rows(conn, d - timedelta(days=6), d) if r.get("sleep_duration_min")]
    sleep_debt = sum(max(0, t.sleep_target_min - r["sleep_duration_min"]) for r in last7)

    rhr_hist = [r["rhr"] for r in prev30 if r.get("rhr") is not None]
    rhr_delta = (
        round(today["rhr"] - sum(rhr_hist) / len(rhr_hist), 1)
        if today.get("rhr") is not None and len(rhr_hist) >= 5 else None
    )

    # Activities strictly before the report day (replaying a past day must not see its own future).
    acts = [dict(r) for r in conn.execute(
        "SELECT * FROM activities WHERE date < ? AND date >= ? ORDER BY date DESC, id DESC",
        (day, (d - timedelta(days=30)).isoformat()),
    )]
    days_since: dict[str, int | None] = {}
    for stype in SESSION_TYPES:
        hard = next((a for a in acts if a["type"] == stype and is_hard(a, t)), None)
        days_since[stype] = (d - date.fromisoformat(hard["date"])).days if hard else None

    week_start = (d - timedelta(days=7)).isoformat()
    week = [a for a in acts if a["date"] >= week_start]
    week_counts = {s: sum(1 for a in week if a["type"] == s) for s in (*SESSION_TYPES, "other")}
    recent = [
        {"date": a["date"], "type": a["type"], "duration_min": a["duration_min"],
         "training_load": a["training_load"], "aerobic_te": a["aerobic_te"], "hard": is_hard(a, t)}
        for a in week
    ]

    has_sleep = bool(today.get("sleep_duration_min"))
    key_fields = ("sleep_score", "hrv_overnight_avg", "training_readiness", "rhr")
    missing = [k for k in key_fields if today.get(k) is None]
    return DayMetrics(
        date=day,
        today=today,
        avg7=_window_avg(prev7),
        avg30=_window_avg(prev30),
        hrv_below_streak=_hrv_streak(last14_desc),
        sleep_debt_7d_min=int(sleep_debt),
        rhr_delta=rhr_delta,
        days_since_hard=days_since,
        recent_activities=recent,
        week_counts=week_counts,
        has_sleep_data=has_sleep,
        has_any_data=bool(today) and len(missing) < len(key_fields),
        missing=missing,
    )
