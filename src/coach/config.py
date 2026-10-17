from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT / "knowledge"
TEMPLATES_DIR = ROOT / "templates"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Thresholds:
    """Numbers behind the safety rules. Defaults are overridden by knowledge/settings.toml."""

    sleep_target_min: int = 480
    short_sleep_min: int = 360
    very_short_sleep_min: int = 300
    hrv_streak_moderate_days: int = 2
    hrv_streak_easy_days: int = 3
    load_ratio_high: float = 1.5
    rhr_delta_moderate: float = 5.0
    readiness_rest_below: float = 25
    readiness_easy_below: float = 40
    body_battery_easy_below: float = 30
    no_back_to_back_hard: bool = True
    hard_aerobic_te: float = 3.5
    hard_anaerobic_te: float = 3.0


@dataclass(frozen=True)
class Settings:
    garmin_email: str | None
    garmin_password: str | None
    gemini_api_key: str | None
    gemini_model: str
    telegram_token: str | None
    telegram_chat_id: str | None
    data_dir: Path
    language: str
    thresholds: Thresholds

    @property
    def db_path(self) -> Path:
        return self.data_dir / "coach.db"

    @property
    def token_dir(self) -> Path:
        return self.data_dir / "garmin_tokens"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)


def load_thresholds(path: Path | None = None) -> tuple[Thresholds, str]:
    """Read knowledge/settings.toml. Returns (thresholds, language)."""
    path = path or KNOWLEDGE_DIR / "settings.toml"
    if not path.exists():
        return Thresholds(), "français"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    overrides = data.get("thresholds", {})
    known = {f.name for f in fields(Thresholds)}
    unknown = set(overrides) - known
    if unknown:
        raise ValueError(f"Unknown keys in {path.name} [thresholds]: {sorted(unknown)}")
    return Thresholds(**overrides), data.get("language", "français")


def get_settings() -> Settings:
    """Read the environment on every call so tests and the CLI always see current values."""
    thresholds, language = load_thresholds()
    return Settings(
        garmin_email=os.getenv("GARMIN_EMAIL") or None,
        garmin_password=os.getenv("GARMIN_PASSWORD") or None,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL") or "gemini-2.5-flash",
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        data_dir=Path(os.getenv("COACH_DATA_DIR") or ROOT / "data"),
        language=language,
        thresholds=thresholds,
    )
