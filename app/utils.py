import re
from datetime import datetime


def parse_user_agent(ua_string):
    """Lightweight dependency-free User-Agent parser.
    Returns dict with browser, os, device (desktop/mobile/tablet).
    Good enough for analytics display; swap for the `user-agents` PyPI
    package if you need more precision.
    """
    ua = ua_string or ""
    ua_l = ua.lower()

    # OS detection
    if "windows" in ua_l:
        os_name = "Windows"
    elif "android" in ua_l:
        os_name = "Android"
    elif "iphone" in ua_l or "ipad" in ua_l or "ios" in ua_l:
        os_name = "iOS"
    elif "mac os" in ua_l or "macintosh" in ua_l:
        os_name = "macOS"
    elif "linux" in ua_l:
        os_name = "Linux"
    else:
        os_name = "Unknown"

    # Browser detection (order matters: Edge/Chrome contain overlapping tokens)
    if "edg/" in ua_l:
        browser = "Edge"
    elif "opr/" in ua_l or "opera" in ua_l:
        browser = "Opera"
    elif "chrome/" in ua_l and "chromium" not in ua_l:
        browser = "Chrome"
    elif "firefox/" in ua_l:
        browser = "Firefox"
    elif "safari/" in ua_l and "chrome/" not in ua_l:
        browser = "Safari"
    else:
        browser = "Unknown"

    # Device detection
    if "mobile" in ua_l and "ipad" not in ua_l:
        device = "Mobile"
    elif "ipad" in ua_l or "tablet" in ua_l:
        device = "Tablet"
    else:
        device = "Desktop"

    return {"browser": browser, "os": os_name, "device": device}


def is_within_business_hours(business_hours_rows):
    """business_hours_rows: list of BusinessHours model instances."""
    if not business_hours_rows:
        return True  # no config means always "online"

    now = datetime.now()
    weekday = now.weekday()  # 0 = Monday
    today_row = next((r for r in business_hours_rows if r.day_of_week == weekday), None)
    if today_row is None:
        return True
    if today_row.is_closed:
        return False
    try:
        open_h, open_m = map(int, today_row.open_time.split(":"))
        close_h, close_m = map(int, today_row.close_time.split(":"))
    except (ValueError, AttributeError):
        return True

    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    now_minutes = now.hour * 60 + now.minute
    return open_minutes <= now_minutes <= close_minutes


def sanitize_text(value, max_len=5000):
    """Basic XSS-safe trimming. Jinja auto-escapes on render; this just
    guards against absurd payloads and strips null bytes."""
    if value is None:
        return ""
    value = str(value).replace("\x00", "")
    return value.strip()[:max_len]


SHORTCUT_RE = re.compile(r"^/[a-zA-Z0-9_-]{1,30}$")


def is_valid_shortcut(shortcut):
    return bool(SHORTCUT_RE.match(shortcut or ""))
