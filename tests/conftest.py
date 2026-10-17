from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from coach import db

FIXTURES = Path(__file__).parent / "fixtures"

GOOD_DAY = {
    "sleep_score": 82, "sleep_duration_min": 450, "hrv_overnight_avg": 61, "hrv_baseline_low": 50,
    "hrv_baseline_high": 68, "hrv_status": "BALANCED", "rhr": 52, "avg_stress": 28,
    "body_battery_wake": 78, "training_readiness": 72, "load_ratio": 1.1,
}


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def sample_raw() -> dict:
    raw = json.loads((FIXTURES / "sample_day.json").read_text(encoding="utf-8"))
    raw.pop("_comment")
    return raw


def add_metrics(conn, day: str, **overrides) -> None:
    db.upsert(conn, "daily_metrics", {**GOOD_DAY, **overrides, "date": day})
    conn.commit()


def add_history(conn, end: str, days: int = 30, **overrides) -> None:
    """`days` normal days ending the day before `end`."""
    d = date.fromisoformat(end)
    for i in range(1, days + 1):
        add_metrics(conn, (d - timedelta(days=i)).isoformat(), **overrides)


def add_activity(conn, day: str, type_: str = "gym", aerobic_te: float = 2.0, anaerobic_te: float = 0.0, id_: int = 1) -> None:
    db.upsert(conn, "activities", {
        "id": id_, "date": day, "type": type_, "type_key": type_, "duration_min": 50,
        "distance_m": None, "avg_hr": 120, "training_load": 80,
        "aerobic_te": aerobic_te, "anaerobic_te": anaerobic_te,
    })
    conn.commit()
