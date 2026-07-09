import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watch import (  # noqa: E402
    is_available,
    looks_like_valid_product_page,
    is_within_window,
    is_first_check_of_session,
    is_last_check_of_session,
    MIN_VALID_PAGE_LENGTH,
)

JST = ZoneInfo("Asia/Tokyo")


def _jst(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str).replace(tzinfo=JST)


def _padded(html: str) -> str:
    """Pad HTML above MIN_VALID_PAGE_LENGTH so length checks don't interfere
    with tests that aren't specifically testing page length."""
    while len(html) < MIN_VALID_PAGE_LENGTH + 100:
        html += "<!-- padding -->"
    return html


# --------------------------------------------------------------------------
# Stock detection: genuine out-of-stock / in-stock pages
# --------------------------------------------------------------------------
def test_out_of_stock_detected():
    html = _padded(
        "<html>Matcha add-to-cart ... This product is currently out of "
        "stock and unavailable. ...</html>"
    )
    assert is_available(html) is False


def test_available_when_marker_absent_and_button_present():
    html = _padded(
        "<html>Matcha add-to-cart ... "
        '<button class="single_add_to_cart_button add_to_cart_button">Add to cart</button>'
        "...</html>"
    )
    assert is_available(html) is True


# --------------------------------------------------------------------------
# False-positive protection: anomalous / anti-bot / partial pages
# --------------------------------------------------------------------------
def test_short_page_is_never_available():
    # Simulates an error page / CAPTCHA / bot-block stub: short, no real content.
    html = "<html><body>Access denied</body></html>"
    assert looks_like_valid_product_page(html) is False
    assert is_available(html) is False


def test_missing_sanity_markers_is_never_available():
    # Long enough, but missing the expected page structure (e.g. a generic
    # error page padded with junk) -> must not be trusted.
    html = "<html>" + ("filler " * 2000) + "</html>"
    assert looks_like_valid_product_page(html) is False
    assert is_available(html) is False


def test_no_marker_but_no_buy_button_is_not_available():
    # Marker absent, page looks valid, but there's no actual purchasable
    # button rendered -> must NOT be treated as available (this is exactly
    # the kind of case that caused the real false positive).
    html = _padded("<html>Matcha add-to-cart ... some other content ...</html>")
    assert looks_like_valid_product_page(html) is True
    assert is_available(html) is False


# --------------------------------------------------------------------------
# Time window logic
# --------------------------------------------------------------------------
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
