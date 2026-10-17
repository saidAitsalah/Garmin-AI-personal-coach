from datetime import date, datetime, timedelta

import pytest

from coach import db, garmin_client, pipeline, telegram
from coach.config import get_settings

TODAY = date(2026, 10, 17)


class FakeGarmin:
    """Counts calls; returns minimal valid payloads. `sleep_ready_after` simulates a late watch sync."""

    def __init__(self, sleep_ready_after: int = 0):
        self.calls: list[str] = []
        self.sleep_calls = 0
        self.sleep_ready_after = sleep_ready_after

    def _rec(self, name, payload):
        self.calls.append(name)
        return payload

    def get_sleep_data(self, d):
        if d == TODAY.isoformat():  # only the morning's night is late; earlier nights are complete
            self.sleep_calls += 1
        seconds = 27000 if d != TODAY.isoformat() or self.sleep_calls > self.sleep_ready_after else 0
        return self._rec("sleep", {"dailySleepDTO": {"sleepTimeSeconds": seconds, "sleepScores": {"overall": {"value": 80}}}})

    def get_hrv_data(self, d):
        return self._rec("hrv", {"hrvSummary": {"lastNightAvg": 60, "baseline": {"balancedLow": 50, "balancedUpper": 70}}})

    def get_stats(self, d):
        return self._rec("stats", {"restingHeartRate": 52, "averageStressLevel": 30})

    def get_training_readiness(self, d):
        return self._rec("readiness", [{"score": 70, "level": "HIGH", "inputContext": "AFTER_WAKEUP_RESET"}])

    def get_training_status(self, d):
        return self._rec("training_status", {})

    def get_respiration_data(self, d):
        return self._rec("respiration", {})

    def get_max_metrics(self, d):
        return self._rec("max_metrics", [])

    def get_activities_by_date(self, start, end):
        return self._rec("activities", [{"activityId": 1, "startTimeLocal": f"{end} 08:00:00",
                                        "activityType": {"typeKey": "running"}, "duration": 1800}])


def test_backfill_twice_downloads_only_the_refresh_window(conn):
    api = FakeGarmin()
    start = TODAY - timedelta(days=9)

    first = garmin_client.sync_range(api, conn, start, TODAY, pause=0, today=TODAY)
    assert first == 10 * len(garmin_client.ENDPOINTS) + 1  # every endpoint per day + one ranged activities call

    api.calls.clear()
    second = garmin_client.sync_range(api, conn, start, TODAY, pause=0, today=TODAY)
    # Only today and yesterday are refreshed (2 days x 7 endpoints); older days are skipped entirely.
    assert api.calls.count("sleep") == 2
    assert second == 2 * len(garmin_client.ENDPOINTS) + 1


def test_a_failing_endpoint_is_retried_next_time_not_stored(conn):
    class Flaky(FakeGarmin):
        def get_hrv_data(self, d):
            raise RuntimeError("503")

    old = TODAY - timedelta(days=10)
    garmin_client.sync_range(Flaky(), conn, old, old, pause=0, today=TODAY)
    assert not db.has_raw(conn, old.isoformat(), "hrv")
    assert db.has_raw(conn, old.isoformat(), "sleep")

    healthy = FakeGarmin()
    garmin_client.sync_range(healthy, conn, old, old, pause=0, today=TODAY)
    assert db.has_raw(conn, old.isoformat(), "hrv") and healthy.calls.count("hrv") == 1


def test_activities_are_split_per_day_and_empty_days_are_marked_fetched(conn):
    old = TODAY - timedelta(days=10)
    garmin_client.sync_range(FakeGarmin(), conn, old - timedelta(days=1), old, pause=0, today=TODAY)
    assert db.has_raw(conn, (old - timedelta(days=1)).isoformat(), "activities")
    assert db.load_raw_day(conn, old.isoformat())["activities"][0]["activityId"] == 1


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("COACH_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def test_run_waits_for_sleep_then_reports(conn, offline):
    api = FakeGarmin(sleep_ready_after=2)  # first two sleep fetches come back empty
    naps = []
    now = datetime(2026, 10, 17, 6, 30)

    outcome = pipeline.run_daily(
        TODAY, conn=conn, api=api, wait_for_sleep=True, use_llm=False, pause=0,
        sleep_fn=naps.append, now_fn=lambda: now,
    )
    assert outcome == "printed"  # Telegram not configured in this test
    assert naps == [600, 600]    # polled twice, 10 minutes apart
    assert conn.execute("SELECT sleep_duration_min FROM daily_metrics WHERE date = ?", (TODAY.isoformat(),)).fetchone()[0] == 450
    assert conn.execute("SELECT sent_at FROM reports").fetchone()["sent_at"] is None


def test_run_gives_up_waiting_at_the_deadline(conn, offline):
    api = FakeGarmin(sleep_ready_after=999)
    clock = iter([datetime(2026, 10, 17, 9, 0), datetime(2026, 10, 17, 9, 5), datetime(2026, 10, 17, 10, 5)])
    naps = []

    pipeline.run_daily(TODAY, conn=conn, api=api, wait_for_sleep=True, use_llm=False, pause=0,
                       sleep_fn=naps.append, now_fn=lambda: next(clock, datetime(2026, 10, 17, 10, 5)))
    row = conn.execute("SELECT body FROM reports WHERE date = ?", (TODAY.isoformat(),)).fetchone()
    assert row is not None and "indisponibles" in row["body"]


def test_report_is_sent_once(conn, monkeypatch, offline):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    sent = []
    monkeypatch.setattr(telegram, "send_message", sent.append)
    kwargs = dict(conn=conn, api=FakeGarmin(), use_llm=False, pause=0, now_fn=lambda: datetime(2026, 10, 17, 8, 0))

    assert pipeline.run_daily(TODAY, **kwargs) == "sent"
    assert pipeline.run_daily(TODAY, **kwargs) == "already_sent"
    assert pipeline.run_daily(TODAY, force=True, **kwargs) == "sent"
    assert len(sent) == 2
    assert get_settings().telegram_configured


def test_dry_run_stores_and_sends_nothing(conn, monkeypatch, offline, capsys):
    monkeypatch.setattr(telegram, "send_message", lambda text: pytest.fail("must not send"))
    pipeline.run_daily(TODAY, conn=conn, api=FakeGarmin(), dry_run=True, use_llm=False, pause=0,
                       now_fn=lambda: datetime(2026, 10, 17, 8, 0))
    assert "Rapport du" in capsys.readouterr().out
    assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0
