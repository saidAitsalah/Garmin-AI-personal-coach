# Coach santé IA

Every morning: Garmin data -> deterministic safety rules -> one Gemini call -> a French report with today's session, sent to Telegram.

```
Garmin Connect --> raw JSON (SQLite) --> daily_metrics / activities --> metrics (trends, sleep debt, HRV streak)
                                                                           |
                                          rules.py: readiness + intensity CEILING (code, not LLM)
                                                                           |
                  knowledge/*.md + metrics + ceiling --> Gemini (1 call, JSON) --> validated against the ceiling
                                                                           |  (retry once, else safe fallback plan)
                                                                           v
                                                      Jinja report --> Telegram (+ stored in SQLite)
```

The LLM only chooses a session *inside* the ceiling that `src/coach/rules.py` computes. A plan that breaks the
rules is rejected, retried once with the reason, and replaced by a conservative fixed plan if it fails again.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env      # then fill in GARMIN_*, GEMINI_API_KEY (and Telegram later)
```

## First run, in this order

| Step | Command | What to check |
|---|---|---|
| 1 | `coach login` | Garmin login (asks for the MFA code once); tokens saved in `data/garmin_tokens/` |
| 2 | `coach backfill --days 60` | Downloads history; run it twice, the second run only refreshes today and yesterday |
| 3 | `coach inspect --date yesterday --endpoint sleep` | **Compare the real payload with the field paths in `src/coach/normalize.py`**; fix any that are off, then `coach rebuild` (no re-download) |
| 4 | `coach report --date yesterday --no-llm` | Readiness level and reasons from the rules alone; do they match how you felt? |
| 5 | Edit `knowledge/goals.md`, `rules.md`, `settings.toml` | Your goals, constraints and thresholds |
| 6 | `coach report --date yesterday` | Same, with the Gemini plan. Replay as many past days as you like; nothing is stored or sent |
| 7 | `coach telegram-setup` | After creating a bot with @BotFather and messaging it, prints your `TELEGRAM_CHAT_ID` |
| 8 | `coach run` | The full morning job; sends the report |
| 9 | `scripts\register_task.ps1` | Runs it every morning (see below) |

Other commands: `coach journal "fatigué, douleur au genou"` (given to the coach; a pain word lowers the ceiling),
`coach sync`, `coach rebuild`, `coach run --dry-run`, `coach run --force` (resend).

## Why it starts after you wake up

Garmin computes the sleep score and overnight HRV once the watch has synced after you wake, so a 5 am collection
would miss them. `coach run --wait-for-sleep` polls every 10 minutes until last night's sleep appears (default limit
10:00, then it sends with a "partial data" notice), and a report is never sent twice for the same day.

## Layout

```
src/coach/
  garmin_client.py  only module that talks to Garmin (tokens, idempotent sync)
  normalize.py      raw JSON -> tables (defensive: missing -> None)
  metrics.py        trends, sleep debt, HRV streak, days since hard session
  rules.py          readiness + intensity ceiling + plan validation
  coach_agent.py    the single LLM call, retry, fallback plans
  llm.py            only module that talks to Gemini
  report.py / telegram.py / pipeline.py / cli.py / db.py / config.py
knowledge/          goals.md, rules.md, principles.md, settings.toml (thresholds)
templates/          morning.html.j2
tests/              37 tests, no network needed (Garmin and Gemini are faked)
```

## Notes

- Data stays local in `data/` (gitignored). Only compact numbers and your knowledge files are sent to Gemini, no name or email.
- `garminconnect` is an unofficial client and is pinned. If Garmin changes its login it may break; all Garmin code is in `garmin_client.py`.
- Default model is `gemini-2.5-flash`; override with `GEMINI_MODEL` in `.env`.
- Not medical advice.
