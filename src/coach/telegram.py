"""Telegram delivery (plain Bot API over HTTPS, no library needed)."""
from __future__ import annotations

import time

import httpx

from .config import get_settings

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4096


class TelegramError(RuntimeError):
    pass


def _chunks(text: str) -> list[str]:
    """Split on blank lines so no message exceeds Telegram's limit."""
    parts, current = [], ""
    for block in text.split("\n\n"):
        if current and len(current) + len(block) + 2 > MAX_LEN:
            parts.append(current)
            current = ""
        current = f"{current}\n\n{block}" if current else block
    parts.append(current)
    return parts


ATTEMPTS = 3
RETRY_PAUSE_S = 3


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """HTTP call that retries dropped connections (resets, timeouts) before giving up.

    Errors never include the URL, which contains the bot token.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return httpx.request(method, url, timeout=20, **kwargs)
        except httpx.TransportError as e:
            if attempt == ATTEMPTS:
                raise TelegramError(
                    f"Could not reach Telegram after {ATTEMPTS} attempts ({type(e).__name__}); "
                    "check the network/VPN/antivirus and retry."
                ) from None
            time.sleep(RETRY_PAUSE_S)
    raise AssertionError("unreachable")


def send_message(text: str) -> None:
    s = get_settings()
    if not s.telegram_configured:
        raise TelegramError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing in .env")
    url = API.format(token=s.telegram_token, method="sendMessage")
    for chunk in _chunks(text):
        r = _request("POST", url, json={
            "chat_id": s.telegram_chat_id, "text": chunk,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        })
        if r.status_code != 200:
            raise TelegramError(f"Telegram refused the message ({r.status_code}): {r.text[:200]}")


def find_chat_id() -> list[tuple[str, str]]:
    """Chats that recently messaged the bot: [(chat_id, label)]. Send your bot a message first."""
    s = get_settings()
    if not s.telegram_token:
        raise TelegramError("TELEGRAM_BOT_TOKEN missing in .env")
    r = _request("GET", API.format(token=s.telegram_token, method="getUpdates"))
    if r.status_code != 200:
        raise TelegramError(f"Telegram error ({r.status_code}): {r.text[:200]}")
    seen: dict[str, str] = {}
    for update in r.json().get("result", []):
        chat = (update.get("message") or {}).get("chat") or {}
        if "id" in chat:
            seen[str(chat["id"])] = chat.get("first_name") or chat.get("title") or chat.get("username") or "?"
    return list(seen.items())
