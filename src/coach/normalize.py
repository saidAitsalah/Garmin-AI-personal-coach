"""Raw Garmin JSON -> daily_metrics / activities rows.

The field paths below come from the shapes returned by Garmin Connect's web API. They have not been
checked against a live account yet: every lookup is defensive (missing -> None), and `coach inspect`
shows the real payload so a path can be fixed here without touching anything else.
Normalisation reads only raw_payloads, so `coach rebuild` can be re-run at any time.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from . import db


def dig(obj: Any, *path: Any, default: Any = None) -> Any:
    """Walk nested dicts/lists; any missing step returns `default`."""
    cur = obj
    for p in path:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list) and isinstance(p, int) and -len(cur) <= p < len(cur):
            cur = cur[p]
        else:
            return default
        if cur is None:
            return default
    return cur


def first(*values: Any) -> Any:
    return next((v for v in values if v is not None), None)


def num(value: Any, ndigits: int = 1) -> float | None:
    try:
        return None if value is None else round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


def minutes(seconds: Any) -> int | None:
    n = num(seconds)
    return round(n / 60) if n else None  # 0 s means "nothing recorded", not "slept 0 min"


def positive(value: Any) -> float | None:
    n = num(value)
    return n if n is not None and n >= 0 else None  # Garmin uses -1 / -2 for "no data"


def _pick_readiness(payload: Any) -> dict[str, Any]:
    entries = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
    entries = [e for e in entries if isinstance(e, dict)]
    for e in entries:
        if e.get("inputContext") == "AFTER_WAKEUP_RESET":
            return e
    return entries[-1] if entries else {}


def _pick_acute_load(training_status: Any) -> dict[str, Any]:
    by_device = dig(training_status, "mostRecentTrainingStatus", "latestTrainingStatusData", default={})
    if not isinstance(by_device, dict) or not by_device:
        return {}
    devices = list(by_device.values())
    primary = next((d for d in devices if isinstance(d, dict) and d.get("primaryTrainingDevice")), None)
    chosen = primary or devices[0]
    return dig(chosen, "acuteTrainingLoadDTO", default={})


def normalize_day(day: str, raw: dict[str, Any]) -> dict[str, Any]:
    sleep = raw.get("sleep") or {}
    dto = sleep.get("dailySleepDTO") or {}
    hrv = dig(raw.get("hrv"), "hrvSummary", default={})
    stats = raw.get("stats") or {}
    resp = raw.get("respiration") or {}
    readiness = _pick_readiness(raw.get("readiness"))
    training_status = raw.get("training_status") or {}
    load = _pick_acute_load(training_status)

    vo2 = first(
        dig(training_status, "mostRecentVO2Max", "generic", "vo2MaxPreciseValue"),
        dig(training_status, "mostRecentVO2Max", "generic", "vo2MaxValue"),
        dig(raw.get("max_metrics"), 0, "generic", "vo2MaxPreciseValue"),
        dig(raw.get("max_metrics"), 0, "generic", "vo2MaxValue"),
    )

    return {
        "date": day,
        "sleep_score": num(dig(dto, "sleepScores", "overall", "value")),
        "sleep_duration_min": minutes(dto.get("sleepTimeSeconds")),
        "deep_min": minutes(dto.get("deepSleepSeconds")),
        "rem_min": minutes(dto.get("remSleepSeconds")),
        "light_min": minutes(dto.get("lightSleepSeconds")),
        "awake_min": minutes(dto.get("awakeSleepSeconds")),
        "hrv_overnight_avg": num(first(hrv.get("lastNightAvg"), sleep.get("avgOvernightHrv"))),
        "hrv_weekly_avg": num(hrv.get("weeklyAvg")),
        "hrv_status": first(hrv.get("status"), sleep.get("hrvStatus")),
        "hrv_baseline_low": num(dig(hrv, "baseline", "balancedLow")),
        "hrv_baseline_high": num(dig(hrv, "baseline", "balancedUpper")),
        "rhr": num(first(stats.get("restingHeartRate"), sleep.get("restingHeartRate"))),
        "avg_stress": positive(stats.get("averageStressLevel")),
        "body_battery_wake": positive(stats.get("bodyBatteryAtWakeTime")),
        "body_battery_high": positive(stats.get("bodyBatteryHighestValue")),
        "respiration_avg": num(first(
            dto.get("averageRespirationValue"),
            resp.get("avgSleepRespirationValue"),
            resp.get("avgWakingRespirationValue"),
        )),
        "vo2max": num(vo2),
        "training_readiness": num(readiness.get("score")),
        "readiness_level": readiness.get("level"),
        "acute_load": num(load.get("dailyTrainingLoadAcute")),
        "chronic_load": num(load.get("dailyTrainingLoadChronic")),
        "load_ratio": num(load.get("dailyAcuteChronicWorkloadRatio"), 2),
        "steps": int(stats["totalSteps"]) if isinstance(stats.get("totalSteps"), (int, float)) else None,
    }


_TYPE_MAP = {
    "gym": {"strength_training", "fitness_equipment", "indoor_cardio", "hiit"},
    "swim": {"lap_swimming", "open_water_swimming", "swimming"},
    "run": {"running", "trail_running", "treadmill_running", "track_running", "virtual_run"},
}


def activity_type(type_key: str | None) -> str:
    key = (type_key or "").lower()
    return next((t for t, keys in _TYPE_MAP.items() if key in keys), "other")


def normalize_activity(a: dict[str, Any], fallback_day: str) -> dict[str, Any] | None:
    if a.get("activityId") is None:
        return None
    type_key = dig(a, "activityType", "typeKey")
    duration_s = num(a.get("duration"))
    return {
        "id": int(a["activityId"]),
        "date": str(a.get("startTimeLocal") or fallback_day)[:10],
        "type": activity_type(type_key),
        "type_key": type_key,
        "duration_min": round(duration_s / 60, 1) if duration_s else None,
        "distance_m": num(a.get("distance")),
        "avg_hr": num(a.get("averageHR")),
        "training_load": num(a.get("activityTrainingLoad")),
        "aerobic_te": num(a.get("aerobicTrainingEffect")),
        "anaerobic_te": num(a.get("anaerobicTrainingEffect")),
    }


def rebuild_day(conn: sqlite3.Connection, day: str) -> None:
    raw = db.load_raw_day(conn, day)
    if not raw:
        return
    db.upsert(conn, "daily_metrics", normalize_day(day, raw))
    conn.execute("DELETE FROM activities WHERE date = ?", (day,))
    for a in raw.get("activities") or []:
        row = normalize_activity(a, day)
        if row:
            db.upsert(conn, "activities", row)
    conn.commit()


def rebuild(conn: sqlite3.Connection, days: list[str] | None = None) -> int:
    """Rebuild normalised tables from raw payloads (all days by default). Returns days processed."""
    if days is None:
        conn.execute("DELETE FROM daily_metrics")
        conn.execute("DELETE FROM activities")
        days = db.raw_days(conn)
    for day in days:
        rebuild_day(conn, day)
    return len(days)
