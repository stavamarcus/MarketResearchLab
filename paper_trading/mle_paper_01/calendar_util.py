"""calendar_util.py — trading-calendar helper for the Daily Offline Runner.

target_date D+1 is the next real NYSE (XNYS) session, not merely the next
weekday. Uses ``exchange_calendars`` (XNYS). The function is injectable so unit
tests can supply a deterministic fake calendar without the dependency.
"""
from __future__ import annotations

from datetime import date, timedelta


class CalendarUnavailable(RuntimeError):
    """Raised when no trading-calendar backend is available."""


def next_session_xnys(business_date: str) -> str:
    """Next XNYS trading session strictly after ``business_date`` (ISO str).

    Raises CalendarUnavailable with an install hint if exchange_calendars is
    missing — we do not fall back to a hand-written holiday list (architect
    decision OQ-1).
    """
    try:
        import exchange_calendars as xc
    except ImportError as e:  # pragma: no cover - environment dependent
        raise CalendarUnavailable(
            "exchange_calendars not installed; run "
            "`pip install exchange_calendars` (no static holiday list is used)"
        ) from e
    cal = xc.get_calendar("XNYS")
    d = date.fromisoformat(business_date)
    # scan forward a bounded window for the next session
    for i in range(1, 12):
        cand = (d + timedelta(days=i)).isoformat()
        if cal.is_session(cand):
            return cand
    raise CalendarUnavailable(
        f"no XNYS session found within 11 days after {business_date}")


def add_sessions(next_session_fn, start_date: str, n: int) -> str:
    """Return the date n XNYS sessions after start_date (n>=0)."""
    d = start_date
    for _ in range(max(0, int(n))):
        d = next_session_fn(d)
    return d


def sessions_until(next_session_fn, start_date: str, end_date: str,
                   max_iter: int = 1000) -> int:
    """Count XNYS trading sessions from start_date (exclusive) to end_date
    (inclusive). 0 if end_date <= start_date. Bounded by max_iter."""
    if not end_date or end_date <= start_date:
        return 0
    n, d = 0, start_date
    while d < end_date and n < max_iter:
        d = next_session_fn(d)
        n += 1
    return n


def last_completed_session_xnys(now=None) -> str:
    """Most recent XNYS session whose CLOSE has already happened (in ET).

    During an in-progress session, today's EOD bar does not exist yet, so the
    last *completed* session is the previous one. `now` may be a datetime/date
    (naive treated as ET) or None for the current ET time."""
    import exchange_calendars as xcals
    import pandas as pd
    cal = xcals.get_calendar("XNYS")
    if now is None:
        now = pd.Timestamp.now(tz="America/New_York")
    else:
        now = pd.Timestamp(now)
        now = (now.tz_localize("America/New_York") if now.tz is None
               else now.tz_convert("America/New_York"))
    sess = cal.date_to_session(now.normalize().tz_localize(None),
                               direction="previous")
    # if today's close has not passed yet, step back to the prior session
    if now < cal.session_close(sess):
        sess = cal.previous_session(sess)
    return str(pd.Timestamp(sess).date())
