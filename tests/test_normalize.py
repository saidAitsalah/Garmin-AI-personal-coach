from coach import db, normalize


def test_normalize_day_extracts_expected_fields(sample_raw):
    row = normalize.normalize_day("2026-10-17", sample_raw)
    assert row["sleep_score"] == 82
    assert row["sleep_duration_min"] == 450
    assert row["deep_min"] == 90
    assert row["hrv_overnight_avg"] == 61
    assert row["hrv_baseline_low"] == 50 and row["hrv_baseline_high"] == 68
    assert row["hrv_status"] == "BALANCED"
    assert row["rhr"] == 52
    assert row["avg_stress"] == 28
    assert row["body_battery_wake"] == 78
    assert row["vo2max"] == 51.4
    assert row["training_readiness"] == 72  # the AFTER_WAKEUP_RESET entry, not the post-exercise one
    assert row["load_ratio"] == 1.11 and row["acute_load"] == 420
    assert row["steps"] == 8421


def test_missing_payloads_give_none_not_errors():
    row = normalize.normalize_day("2026-10-17", {})
    assert row["date"] == "2026-10-17"
    assert all(v is None for k, v in row.items() if k != "date")


def test_unsynced_sleep_and_negative_stress_are_none(sample_raw):
    sample_raw["sleep"]["dailySleepDTO"]["sleepTimeSeconds"] = 0
    sample_raw["stats"]["averageStressLevel"] = -1
    row = normalize.normalize_day("2026-10-17", sample_raw)
    assert row["sleep_duration_min"] is None
    assert row["avg_stress"] is None


def test_activity_types_and_dates(sample_raw):
    acts = [normalize.normalize_activity(a, "2026-10-16") for a in sample_raw["activities"]]
    assert [a["type"] for a in acts] == ["gym", "swim"]
    assert acts[0]["date"] == "2026-10-16"
    assert acts[0]["duration_min"] == 60.0
    assert normalize.activity_type("trail_running") == "run"
    assert normalize.activity_type("yoga") == "other"
    assert normalize.normalize_activity({"no": "id"}, "2026-10-16") is None


def test_rebuild_from_raw_is_repeatable(conn, sample_raw):
    for endpoint, payload in sample_raw.items():
        if endpoint != "activities":
            db.store_raw(conn, "2026-10-17", endpoint, payload)
    db.store_raw(conn, "2026-10-16", "activities", sample_raw["activities"])

    assert normalize.rebuild(conn) == 2
    assert normalize.rebuild(conn) == 2  # idempotent: no duplicate rows
    assert conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 2
