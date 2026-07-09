#!/usr/bin/env python3
"""
matcha-watch
------------
Checks stock availability for Marukyu Koyamaen's Wako and Isuzu matcha and
sends a Telegram notification whenever either one becomes available.

Also sends a "session opened" message on the first check of the day and a
"session closed" message on the last check of the day (Mon-Fri, 9:00-17:30 JST).

Designed to run as a GitHub Action (cron every 2 min, Mon-Fri 9:00-17:30 JST).
State is kept in a JSON file committed back to the repo so notifications only
fire on state transitions (out of stock -> available) and once per day for
the open/close messages.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# --------------------------------------------------------------------------
# Products to watch
# --------------------------------------------------------------------------
PRODUCTS = {
    "wako": {
        "name": "Wako",
        "url": "https://www.marukyu-koyamaen.co.jp/english/shop/products/1161020c1",
    },
    "isuzu": {
        "name": "Isuzu",
        "url": "https://www.marukyu-koyamaen.co.jp/english/shop/products/1191040c1",
    },
}

OUT_OF_STOCK_MARKER = "currently out of stock and unavailable"

STATE_FILE = Path(__file__).resolve().parent.parent / "state" / "state.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

TIMEOUT_SECONDS = 20
MAX_RETRIES = 2

JST = ZoneInfo("Asia/Tokyo")
WINDOW_START = (9, 0)     # 9:00 AM JST
WINDOW_END = (17, 30)     # 5:30 PM JST
CHECK_INTERVAL_MINUTES = 2


# --------------------------------------------------------------------------
# Persistent state
# --------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[warn] state.json is corrupted, starting fresh", file=sys.stderr)
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Session window helpers (Mon-Fri, 9:00-17:30 JST)
# --------------------------------------------------------------------------
def now_jst() -> datetime:
    return datetime.now(JST)


def is_within_window(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    start = dt.replace(hour=WINDOW_START[0], minute=WINDOW_START[1], second=0, microsecond=0)
    end = dt.replace(hour=WINDOW_END[0], minute=WINDOW_END[1], second=0, microsecond=0)
    return start <= dt <= end


def is_first_check_of_session(dt: datetime) -> bool:
    """True if dt is within the first CHECK_INTERVAL_MINUTES of the window opening."""
    start = dt.replace(hour=WINDOW_START[0], minute=WINDOW_START[1], second=0, microsecond=0)
    minutes_since_start = (dt - start).total_seconds() / 60
    return 0 <= minutes_since_start < CHECK_INTERVAL_MINUTES


def is_last_check_of_session(dt: datetime) -> bool:
    """True if dt is within the last CHECK_INTERVAL_MINUTES of the window closing."""
    end = dt.replace(hour=WINDOW_END[0], minute=WINDOW_END[1], second=0, microsecond=0)
    minutes_until_end = (end - dt).total_seconds() / 60
    return 0 <= minutes_until_end < CHECK_INTERVAL_MINUTES


# --------------------------------------------------------------------------
# Stock check
# --------------------------------------------------------------------------
def fetch_page(url: str) -> str | None:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"[warn] attempt {attempt}/{MAX_RETRIES} failed for {url}: {exc}", file=sys.stderr)
            time.sleep(2)
    print(f"[error] could not fetch {url}: {last_error}", file=sys.stderr)
    return None


def is_available(html: str) -> bool:
    """
    The out-of-stock marker is a fixed text string on the product page.
    If it's NOT present, we assume at least one size/variant is available
    (policy: notify if ANY size is in stock).
    """
    return OUT_OF_STOCK_MARKER not in html


# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------
def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[error] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment", file=sys.stderr)
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(api_url, data=payload, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[error] failed to send Telegram message: {exc}", file=sys.stderr)
        return False


def build_stock_notification(product: dict) -> str:
    return (
        f"🍵 <b>{product['name']}</b> is now IN STOCK\n"
        f"{product['url']}\n\n"
        f"Detected by matcha-watch."
    )


def build_session_open_message(dt: datetime) -> str:
    return (
        f"▶️ <b>matcha-watch session started</b>\n"
        f"Checking every {CHECK_INTERVAL_MINUTES} minutes until "
        f"{WINDOW_END[0]:02d}:{WINDOW_END[1]:02d} JST.\n"
        f"({dt.strftime('%A, %Y-%m-%d %H:%M')} JST)"
    )


def build_session_close_message(dt: datetime) -> str:
    return (
        f"⏹️ <b>matcha-watch session ended</b>\n"
        f"No more checks today. Resuming tomorrow at "
        f"{WINDOW_START[0]:02d}:{WINDOW_START[1]:02d} JST"
        f"{' (Monday)' if dt.weekday() == 4 else ''}.\n"
        f"({dt.strftime('%A, %Y-%m-%d %H:%M')} JST)"
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> int:
    dt = now_jst()

    if not is_within_window(dt):
        print(f"[info] {dt.isoformat()} is outside the Mon-Fri 9:00-17:30 JST window, skipping.")
        return 0

    state = load_state()
    exit_code = 0

    # --- Session open notification (once per day, first run of the window) ---
    session_state = state.setdefault("_session", {})
    today_str = dt.strftime("%Y-%m-%d")

    if is_first_check_of_session(dt) and session_state.get("opened_on") != today_str:
        if send_telegram_message(build_session_open_message(dt)):
            session_state["opened_on"] = today_str
        else:
            exit_code = 1

    # --- Stock checks ---
    for key, product in PRODUCTS.items():
        html = fetch_page(product["url"])
        if html is None:
            # Could not check this product this run; leave its state untouched.
            exit_code = 1
            continue

        available_now = is_available(html)
        was_available = state.get(key, {}).get("available", False)

        print(f"[info] {product['name']}: available={available_now} (previous={was_available})")

        # Notify only on the out-of-stock -> available transition (avoids spam)
        if available_now and not was_available:
            if not send_telegram_message(build_stock_notification(product)):
                exit_code = 1

        state[key] = {
            "available": available_now,
            "last_checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    # --- Session close notification (once per day, last run of the window) ---
    if is_last_check_of_session(dt) and session_state.get("closed_on") != today_str:
        if send_telegram_message(build_session_close_message(dt)):
            session_state["closed_on"] = today_str
        else:
            exit_code = 1

    save_state(state)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
