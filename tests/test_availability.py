import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watch import (  # noqa: E402
    is_available,
    is_within_window,
    is_first_check_of_session,
    is_last_check_of_session,
)

JST = ZoneInfo("Asia/Tokyo")


def _jst(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str).replace(tzinfo=JST)


def test_out_of_stock_detected():
    html = "<html>... This product is currently out of stock and unavailable. ...</html>"
    assert is_available(html) is False


def test_available_when_marker_absent():
    html = "<html>... Add to cart ... </html>"
    assert is_available(html) is True


def test_window_monday_9am_is_open():
    assert is_within_window(_jst("2026-07-13T09:00:00")) is True


def test_window_monday_859am_is_closed():
    assert is_within_window(_jst("2026-07-13T08:59:00")) is False


def test_window_friday_530pm_is_open():
    assert is_within_window(_jst("2026-07-17T17:30:00")) is True


def test_window_friday_531pm_is_closed():
    assert is_within_window(_jst("2026-07-17T17:31:00")) is False


def test_window_saturday_is_closed():
    assert is_within_window(_jst("2026-07-18T12:00:00")) is False


def test_window_sunday_is_closed():
    assert is_within_window(_jst("2026-07-12T12:00:00")) is False


def test_first_check_of_session_at_open():
    assert is_first_check_of_session(_jst("2026-07-13T09:00:00")) is True
    assert is_first_check_of_session(_jst("2026-07-13T09:01:59")) is True
    assert is_first_check_of_session(_jst("2026-07-13T09:02:00")) is False


def test_last_check_of_session_at_close():
    assert is_last_check_of_session(_jst("2026-07-13T17:30:00")) is True
    assert is_last_check_of_session(_jst("2026-07-13T17:28:30")) is True
    assert is_last_check_of_session(_jst("2026-07-13T17:27:59")) is False


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} tests passed")
