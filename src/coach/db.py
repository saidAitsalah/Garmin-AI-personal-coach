from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import get_settings

SCHEMA = Path(__file__).with_name("schema.sql")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = path or get_settings().db_path
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def upsert(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    """INSERT OR REPLACE a row. Table and column names come from our own code, never user input."""
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


# --- raw payloads -------------------------------------------------------------

def has_raw(conn: sqlite3.Connection, day: str, endpoint: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM raw_payloads WHERE date = ? AND endpoint = ?", (day, endpoint)
    ).fetchone() is not None


def store_raw(conn: sqlite3.Connection, day: str, endpoint: str, payload: Any) -> None:
    upsert(conn, "raw_payloads", {
        "date": day, "endpoint": endpoint,
        "json": json.dumps(payload, ensure_ascii=False), "fetched_at": now_iso(),
    })
    conn.commit()


def load_raw_day(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    rows = conn.execute("SELECT endpoint, json FROM raw_payloads WHERE date = ?", (day,)).fetchall()
    return {r["endpoint"]: json.loads(r["json"]) for r in rows}


def raw_days(conn: sqlite3.Connection) -> list[str]:
    return [r["date"] for r in conn.execute("SELECT DISTINCT date FROM raw_payloads ORDER BY date")]


# --- journal ------------------------------------------------------------------

def add_journal(conn: sqlite3.Connection, day: str, text: str) -> None:
    conn.execute("INSERT INTO journal (date, text, created_at) VALUES (?, ?, ?)", (day, text, now_iso()))
    conn.commit()


def journal_text(conn: sqlite3.Connection, day: str) -> str:
    rows = conn.execute("SELECT text FROM journal WHERE date = ? ORDER BY id", (day,)).fetchall()
    return "\n".join(r["text"] for r in rows)


# --- plans & reports ----------------------------------------------------------

def save_plan(conn: sqlite3.Connection, day: str, plan_json: str, prompt_version: str, source: str) -> None:
    upsert(conn, "plans", {
        "date": day, "prompt_version": prompt_version, "source": source,
        "json": plan_json, "created_at": now_iso(),
    })
    conn.commit()


def recent_plans(conn: sqlite3.Connection, day: str, n: int = 3) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT date, json FROM plans WHERE date < ? ORDER BY date DESC LIMIT ?", (day, n)
    ).fetchall()
    return [{"date": r["date"], **json.loads(r["json"])} for r in rows]


def save_report(conn: sqlite3.Connection, day: str, body: str, sent: bool) -> None:
    upsert(conn, "reports", {
        "date": day, "body": body, "created_at": now_iso(), "sent_at": now_iso() if sent else None,
    })
    conn.commit()


def report_sent(conn: sqlite3.Connection, day: str) -> bool:
    row = conn.execute("SELECT sent_at FROM reports WHERE date = ?", (day,)).fetchone()
    return bool(row and row["sent_at"])
