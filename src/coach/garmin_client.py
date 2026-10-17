"""The only module that talks to Garmin. Everything else works from the raw payloads stored in SQLite.

`garminconnect` is an unofficial client: Garmin can change its login or endpoints at any time.
Keeping all calls here (and the version pinned in pyproject.toml) limits the blast radius.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

from . import db
from .config import Settings, get_settings

log = logging.getLogger(__name__)

# endpoint name (as stored in raw_payloads) -> garminconnect method taking a 'YYYY-MM-DD' string
ENDPOINTS: dict[str, str] = {
    "sleep": "get_sleep_data",
    "hrv": "get_hrv_data",
    "stats": "get_stats",
    "readiness": "get_training_readiness",
    "training_status": "get_training_status",
    "respiration": "get_respiration_data",
    "max_metrics": "get_max_metrics",
}
ACTIVITIES = "activities"
ALL_ENDPOINTS = [*ENDPOINTS, ACTIVITIES]

# Today's and yesterday's data keep changing (sleep finishes processing, activities sync late),
# so those days are always re-fetched; older days are fetched once.
REFRESH_DAYS = 1


class GarminError(RuntimeError):
    """Anything that stops us from getting Garmin data; the message says what to do."""


def _ask_mfa() -> str:
    if not sys.stdin or not sys.stdin.isatty():
        raise GarminError("Garmin asks for an MFA code. Run `coach login` once in a terminal.")
    return input("Garmin MFA code: ").strip()


def login(settings: Settings | None = None) -> Garmin:
    """Log in, reusing saved tokens when present. The first login saves them under data/garmin_tokens."""
    s = settings or get_settings()
    token_dir = s.token_dir
    has_tokens = (token_dir / "garmin_tokens.json").exists()
    if not has_tokens and not (s.garmin_email and s.garmin_password):
        raise GarminError("Set GARMIN_EMAIL and GARMIN_PASSWORD in .env, then run `coach login`.")
    api = Garmin(s.garmin_email, s.garmin_password, prompt_mfa=_ask_mfa)
    try:
        api.login(str(token_dir))
    except GarminConnectTooManyRequestsError as e:
        raise GarminError(f"Garmin rate limit hit; wait a few minutes. ({e})") from e
    except GarminConnectAuthenticationError as e:
        raise GarminError(f"Garmin login failed: {e}") from e
    return api


# --- fetching -----------------------------------------------------------------

class _Failed:
    """Sentinel: the call failed, store nothing so it is retried next time."""


FAILED = _Failed()


def _call(api: Any, method: str, *args: Any) -> Any:
    try:
        return getattr(api, method)(*args)
    except (GarminConnectTooManyRequestsError, GarminConnectAuthenticationError):
        raise
    except Exception as e:  # one broken endpoint must not kill the whole sync
        log.warning("Garmin %s%s failed: %s", method, args, e)
        return FAILED


def _needs(conn: sqlite3.Connection, day: str, endpoint: str, today: date) -> bool:
    age = (today - date.fromisoformat(day)).days
    return age <= REFRESH_DAYS or not db.has_raw(conn, day, endpoint)


def sync_range(
    api: Any,
    conn: sqlite3.Connection,
    start: date,
    end: date,
    *,
    pause: float = 1.0,
    today: date | None = None,
) -> int:
    """Fetch what is missing (plus the last REFRESH_DAYS days) for start..end. Returns API calls made."""
    today = today or date.today()
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    calls = 0
    try:
        for day in days:
            for endpoint, method in ENDPOINTS.items():
                if not _needs(conn, day, endpoint, today):
                    continue
                payload = _call(api, method, day)
                calls += 1
                if payload is not FAILED:
                    db.store_raw(conn, day, endpoint, payload)
                time.sleep(pause)
        calls += _sync_activities(api, conn, days, today)
    except GarminConnectTooManyRequestsError as e:
        raise GarminError(f"Garmin rate limit hit after {calls} calls; retry later. ({e})") from e
    except GarminConnectAuthenticationError as e:
        raise GarminError(f"Garmin session rejected; run `coach login`. ({e})") from e
    return calls


def _sync_activities(api: Any, conn: sqlite3.Connection, days: list[str], today: date) -> int:
    """One ranged call for all days that need activities, then split per day (empty days stored as [])."""
    missing = [d for d in days if _needs(conn, d, ACTIVITIES, today)]
    if not missing:
        return 0
    first, last = min(missing), max(missing)
    activities = _call(api, "get_activities_by_date", first, last)
    if activities is FAILED:
        return 1
    by_day: dict[str, list[Any]] = defaultdict(list)
    for a in activities or []:
        start_local = str(a.get("startTimeLocal") or "")[:10]
        if start_local:
            by_day[start_local].append(a)
    for day in missing:
        db.store_raw(conn, day, ACTIVITIES, by_day.get(day, []))
    time.sleep(1.0)
    return 1
