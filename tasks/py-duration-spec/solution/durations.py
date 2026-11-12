"""Human-friendly durations, as used in config files (e.g. `timeout = "1h30m"`)."""

import re

_UNITS = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
_PART = re.compile(r"\s*(\d+)([dhms])", re.IGNORECASE)


def parse_duration(text: str) -> int:
    """Return the number of seconds in a duration string (see repo docstring for spec)."""
    s = text.strip()
    if not s:
        raise ValueError("empty duration")
    if s.isdigit():
        return int(s)
    pos, total, last_rank = 0, 0, -1
    order = {u: i for i, (u, _) in enumerate(_UNITS)}
    seconds = dict(_UNITS)
    while pos < len(s):
        m = _PART.match(s, pos)
        if not m:
            raise ValueError(f"invalid duration: {text!r}")
        unit = m.group(2).lower()
        if order[unit] <= last_rank:
            raise ValueError(f"units out of order or repeated: {text!r}")
        last_rank = order[unit]
        total += int(m.group(1)) * seconds[unit]
        pos = m.end()
    return total


def format_duration(seconds: int) -> str:
    """Format seconds as the shortest canonical duration string."""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
        raise ValueError(f"invalid seconds: {seconds!r}")
    if seconds == 0:
        return "0s"
    parts = []
    for unit, size in _UNITS:
        n, seconds = divmod(seconds, size)
        if n:
            parts.append(f"{n}{unit}")
    return "".join(parts)
