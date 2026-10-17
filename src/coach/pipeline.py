"""End-to-end orchestration: sync -> normalise -> metrics -> rules -> coach -> report -> delivery."""
from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from . import coach_agent, db, garmin_client, metrics, normalize, report, rules, telegram
from .config import get_settings

log = logging.getLogger(__name__)

SYNC_WINDOW_DAYS = 2  # day itself + the two before it (older gaps are filled by `coach sync`)


def build_report(
    conn: sqlite3.Connection, day: str, *, use_llm: bool = True, persist: bool = False
) -> report.Report:
    """Build the report for `day` from stored data only (this is also the replay mode)."""
    t = get_settings().thresholds
    m = metrics.compute(conn, day, t)
    journal = db.journal_text(conn, day)
    readiness = rules.assess(m, t, journal)
    plan, source = coach_agent.generate_plan(
        m, readiness, journal, db.recent_plans(conn, day), use_llm=use_llm
    )
    if persist:
        db.save_plan(conn, day, plan.model_dump_json(), coach_agent.PROMPT_VERSION, source)
    return report.render(day, m, readiness, plan, source)


def sync_and_normalize(api: Any, conn: sqlite3.Connection, start: date, end: date, *, pause: float = 1.0,
                       today: date | None = None) -> int:
    calls = garmin_client.sync_range(api, conn, start, end, pause=pause, today=today)
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    normalize.rebuild(conn, days)
    return calls


def _has_sleep(conn: sqlite3.Connection, day: str) -> bool:
    row = conn.execute("SELECT sleep_duration_min FROM daily_metrics WHERE date = ?", (day,)).fetchone()
    return bool(row and row["sleep_duration_min"])


def run_daily(
    day: date,
    *,
    conn: sqlite3.Connection | None = None,
    api: Any = None,
    wait_for_sleep: bool = False,
    until: str = "10:00",
    poll_min: float = 10,
    dry_run: bool = False,
    force: bool = False,
    use_llm: bool = True,
    pause: float = 1.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], datetime] = datetime.now,
) -> str:
    """Morning job. Returns 'already_sent', 'printed' (dry run / Telegram not set up) or 'sent'."""
    conn = conn or db.connect()
    iso = day.isoformat()
    if not dry_run and not force and db.report_sent(conn, iso):
        log.info("Report for %s already sent; use --force to resend.", iso)
        return "already_sent"

    api = api or garmin_client.login()
    deadline = datetime.combine(day, datetime.strptime(until, "%H:%M").time())
    while True:
        sync_and_normalize(api, conn, day - timedelta(days=SYNC_WINDOW_DAYS), day, pause=pause,
                           today=now_fn().date())
        if _has_sleep(conn, iso) or not wait_for_sleep:
            break
        if now_fn() >= deadline:
            log.warning("Sleep data still missing at %s: sending with partial data.", until)
            break
        log.info("Sleep data not on Garmin yet; checking again in %s min.", poll_min)
        sleep_fn(poll_min * 60)

    rep = build_report(conn, iso, use_llm=use_llm, persist=not dry_run)
    if dry_run:
        print(rep.plain)
        return "printed"

    if not get_settings().telegram_configured:
        db.save_report(conn, iso, rep.html, sent=False)
        print(rep.plain)
        log.warning("Telegram not configured: report stored but not sent.")
        return "printed"

    telegram.send_message(rep.html)
    db.save_report(conn, iso, rep.html, sent=True)
    return "sent"
