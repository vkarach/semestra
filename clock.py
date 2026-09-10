import logging
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

_NOW_ENV = "SEMESTRA_CLOCK_NOW"
_OFFSET_ENV = "SEMESTRA_CLOCK_OFFSET"
_OFFSET_RE = re.compile(r"([+-])?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")

_offset: timedelta | None = None


def _parse_offset(raw: str) -> timedelta:
    raw = raw.strip()
    m = _OFFSET_RE.fullmatch(raw)
    if not m or not any(m.group(i) for i in (2, 3, 4, 5)):
        if raw:
            log.warning("bad %s %r, ignoring", _OFFSET_ENV, raw)
        return timedelta()
    sign, d, h, mi, s = m.groups()
    delta = timedelta(days=int(d or 0), hours=int(h or 0),
                      minutes=int(mi or 0), seconds=int(s or 0))
    return -delta if sign == "-" else delta


def _compute_offset() -> timedelta:
    anchor = os.getenv(_NOW_ENV, "").strip()
    if anchor:
        try:
            return datetime.fromisoformat(anchor) - datetime.now().replace(microsecond=0)
        except ValueError:
            log.warning("bad %s %r, ignoring", _NOW_ENV, anchor)
    return _parse_offset(os.getenv(_OFFSET_ENV, ""))


def _get_offset() -> timedelta:
    global _offset
    if _offset is None:
        _offset = _compute_offset()
        if _offset:
            log.warning("clock offset active: %s", _offset)
    return _offset


def now(tz: str) -> datetime:
    return (datetime.now(ZoneInfo(tz)) + _get_offset()).replace(tzinfo=None)
