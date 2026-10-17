from coach import metrics, rules
from coach.config import Thresholds

from conftest import add_activity, add_history, add_metrics

T = Thresholds()
DAY = "2026-10-17"


def assess(conn, journal=""):
    m = metrics.compute(conn, DAY, T)
    return m, rules.assess(m, T, journal)


def test_healthy_day_has_no_cap(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY)
    _, r = assess(conn)
    assert r.ceiling == "hard" and r.level == "green" and r.reasons == []
    assert r.score is not None and r.score > 70


def test_hrv_streak_lowers_ceiling(conn):
    add_history(conn, DAY)
    for day in ("2026-10-15", "2026-10-16", DAY):
        add_metrics(conn, day, hrv_overnight_avg=40)
    m, r = assess(conn)
    assert m.hrv_below_streak == 3
    assert r.ceiling == "easy"


def test_hrv_streak_is_broken_by_a_normal_night(conn):
    add_history(conn, DAY)
    add_metrics(conn, "2026-10-16", hrv_overnight_avg=60)
    add_metrics(conn, DAY, hrv_overnight_avg=40)
    m, r = assess(conn)
    assert m.hrv_below_streak == 1 and r.ceiling == "hard"


def test_short_sleep_blocks_heavy_strength(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, sleep_duration_min=330)
    m, r = assess(conn)
    assert r.ceiling == "moderate"
    assert r.type_caps["gym"] == "moderate"
    # 6 previous nights of 450 min (30 min short of the 480 target each) + today 150 short
    assert m.sleep_debt_7d_min == 6 * 30 + 150


def test_very_short_sleep_is_easy_only(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, sleep_duration_min=240)
    assert assess(conn)[1].ceiling == "easy"


def test_high_load_ratio_reduces_volume(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, load_ratio=1.7)
    _, r = assess(conn)
    assert r.ceiling == "moderate" and r.notes


def test_elevated_resting_hr(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, rhr=60)
    m, r = assess(conn)
    assert m.rhr_delta == 8.0 and r.ceiling == "moderate"


def test_low_readiness_forces_rest(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, training_readiness=15)
    _, r = assess(conn)
    assert r.ceiling == "rest" and r.level == "red"


def test_hard_session_yesterday_blocks_another_hard_day(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY)
    add_activity(conn, "2026-10-16", "run", aerobic_te=4.2)
    m, r = assess(conn)
    assert m.days_since_hard["run"] == 1
    assert r.ceiling == "moderate"


def test_easy_session_yesterday_does_not_cap(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY)
    add_activity(conn, "2026-10-16", "run", aerobic_te=2.0)
    assert assess(conn)[1].ceiling == "hard"


def test_replay_ignores_activities_from_the_report_day(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY)
    add_activity(conn, DAY, "run", aerobic_te=4.5)
    assert metrics.compute(conn, DAY, T).days_since_hard["run"] is None


def test_pain_in_journal_caps_and_adds_guidance(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY)
    _, r = assess(conn, journal="Douleur au genou gauche")
    assert r.ceiling == "moderate" and r.notes


def test_missing_data_is_cautious(conn):
    _, r = assess(conn)
    assert r.ceiling == "moderate"


def test_most_restrictive_rule_wins(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, sleep_duration_min=330, training_readiness=30, load_ratio=1.8)
    assert assess(conn)[1].ceiling == "easy"


def test_violations(conn):
    add_history(conn, DAY)
    add_metrics(conn, DAY, sleep_duration_min=330)
    _, r = assess(conn)

    class P:
        def __init__(self, s, i):
            self.session_type, self.intensity = s, i

    assert r.violations(P("run", "hard"))
    assert r.violations(P("gym", "hard"))
    assert not r.violations(P("gym", "moderate"))
    assert not r.violations(P("rest", "easy"))
    assert r.violations(P("recovery", "hard"))

    add_metrics(conn, DAY, training_readiness=10)
    _, rest_day = assess(conn)
    assert rest_day.violations(P("run", "easy"))
    assert not rest_day.violations(P("recovery", "easy"))
