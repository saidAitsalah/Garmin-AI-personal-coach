from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from logging.handlers import RotatingFileHandler
from typing import Annotated

import typer

from . import db, garmin_client, normalize, pipeline, telegram
from .config import get_settings

app = typer.Typer(help="AI health coach: Garmin -> safety rules -> coach LLM -> morning report.",
                  no_args_is_help=True, add_completion=False)

DateOpt = Annotated[str, typer.Option("--date", "-d", help="YYYY-MM-DD, 'today' or 'yesterday'")]


def parse_day(value: str) -> date:
    if value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(f"'{value}' is not a date (use YYYY-MM-DD, today or yesterday)") from None


@app.callback()
def main() -> None:
    # Windows consoles default to cp1252 and choke on the arrows/emoji in reports.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    log_dir = get_settings().log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), RotatingFileHandler(log_dir / "coach.log", maxBytes=1_000_000,
                                                               backupCount=3, encoding="utf-8")],
    )
    # httpx logs full request URLs at INFO, and Telegram's URL contains the bot token.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _fail(e: Exception) -> typer.Exit:
    typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
    return typer.Exit(1)


@app.command()
def login() -> None:
    """First Garmin login (asks for the MFA code if needed) and saves the session tokens."""
    try:
        api = garmin_client.login()
    except garmin_client.GarminError as e:
        raise _fail(e) from e
    typer.echo(f"Logged in as {getattr(api, 'full_name', '') or 'your Garmin account'}. Tokens saved.")


@app.command()
def backfill(days: Annotated[int, typer.Option(help="How many days of history to download")] = 60,
             pause: Annotated[float, typer.Option(help="Seconds between Garmin calls")] = 1.0) -> None:
    """Download history (skips what is already stored), then build the normalised tables."""
    conn = db.connect()
    try:
        api = garmin_client.login()
        end = date.today()
        calls = pipeline.sync_and_normalize(api, conn, end - timedelta(days=days - 1), end, pause=pause)
    except garmin_client.GarminError as e:
        raise _fail(e) from e
    n_days = conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    typer.echo(f"Done: {calls} Garmin calls. {n_days} days in daily_metrics.")


@app.command()
def sync(date_: DateOpt = "today",
         back: Annotated[int, typer.Option(help="Also sync this many days before")] = 2) -> None:
    """Fetch recent days from Garmin and refresh the normalised tables."""
    day = parse_day(date_)
    conn = db.connect()
    try:
        calls = pipeline.sync_and_normalize(garmin_client.login(), conn, day - timedelta(days=back), day)
    except garmin_client.GarminError as e:
        raise _fail(e) from e
    typer.echo(f"Done: {calls} Garmin calls.")


@app.command()
def rebuild() -> None:
    """Rebuild daily_metrics and activities from the stored raw payloads (no network)."""
    conn = db.connect()
    n = normalize.rebuild(conn)
    typer.echo(f"Rebuilt {n} days.")


@app.command()
def inspect(date_: DateOpt = "today",
            endpoint: Annotated[str, typer.Option(help=f"One of {', '.join(garmin_client.ALL_ENDPOINTS)}")] = "sleep",
            keys_only: Annotated[bool, typer.Option(help="Print only the top-level structure")] = False) -> None:
    """Show a stored raw Garmin payload (to check/fix field paths in normalize.py)."""
    conn = db.connect()
    raw = db.load_raw_day(conn, parse_day(date_).isoformat())
    if endpoint not in raw:
        raise _fail(RuntimeError(f"No '{endpoint}' payload stored for that day. Have: {sorted(raw) or 'nothing'}"))
    payload = raw[endpoint]
    if keys_only:
        payload = {k: type(v).__name__ for k, v in payload.items()} if isinstance(payload, dict) else type(payload).__name__
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2)[:20000])


@app.command()
def report(date_: DateOpt = "today",
           no_llm: Annotated[bool, typer.Option(help="Skip the LLM: show rules + fallback plan")] = False,
           send: Annotated[bool, typer.Option(help="Also store the plan, send to Telegram, mark as sent")] = False) -> None:
    """Build the report for a day from stored data (replay mode). Prints only, unless --send."""
    conn = db.connect()
    rep = pipeline.build_report(conn, parse_day(date_).isoformat(), use_llm=not no_llm, persist=send)
    typer.echo(rep.plain)
    if send:
        try:
            telegram.send_message(rep.html)
        except telegram.TelegramError as e:
            raise _fail(e) from e
        db.save_report(conn, parse_day(date_).isoformat(), rep.html, sent=True)
        typer.echo("\nSent.")


@app.command()
def run(date_: DateOpt = "today",
        wait_for_sleep: Annotated[bool, typer.Option(help="Poll Garmin until last night's sleep has synced")] = False,
        until: Annotated[str, typer.Option(help="Give up waiting at this local time (HH:MM)")] = "10:00",
        poll_min: Annotated[float, typer.Option(help="Minutes between checks")] = 10,
        dry_run: Annotated[bool, typer.Option(help="Print the report; store and send nothing")] = False,
        force: Annotated[bool, typer.Option(help="Send even if today's report was already sent")] = False,
        no_llm: Annotated[bool, typer.Option(help="Skip the LLM (rules + fallback plan)")] = False) -> None:
    """The morning job: sync Garmin, build the report, send it."""
    try:
        outcome = pipeline.run_daily(parse_day(date_), wait_for_sleep=wait_for_sleep, until=until,
                                     poll_min=poll_min, dry_run=dry_run, force=force, use_llm=not no_llm)
    except (garmin_client.GarminError, telegram.TelegramError) as e:
        raise _fail(e) from e
    typer.echo(f"\n[{outcome}]")


@app.command()
def journal(text: Annotated[str, typer.Argument(help="How you feel: fatigue, pain, mood, constraints")],
            date_: DateOpt = "today") -> None:
    """Add a journal note for a day; it is given to the coach and can lower the day's ceiling."""
    db.add_journal(db.connect(), parse_day(date_).isoformat(), text)
    typer.echo("Saved.")


@app.command("telegram-setup")
def telegram_setup() -> None:
    """Find your Telegram chat id (send any message to your bot first)."""
    try:
        chats = telegram.find_chat_id()
    except telegram.TelegramError as e:
        raise _fail(e) from e
    if not chats:
        typer.echo("No messages found. Send your bot a message in Telegram, then run this again.")
        raise typer.Exit(1)
    for chat_id, label in chats:
        typer.echo(f"TELEGRAM_CHAT_ID={chat_id}   ({label})")


if __name__ == "__main__":
    app()
