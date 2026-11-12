"""Parsing of size and boolean values."""

import re

from ingestd.config.errors import ConfigError

_SIZE_RE = re.compile(r"^\s*(\d+)\s*([A-Za-z]*)\s*$")
_UNITS = {
    "": 1,
    "b": 1,
    "k": 1000,
    "kb": 1000,
    "kib": 1024,
    "m": 1000**2,
    "mb": 1000**2,
    "mib": 1024**2,
    "g": 1000**3,
    "gb": 1000**3,
    "gib": 1024**3,
}


def parse_size(value):
    """'8MiB' -> 8388608, '64k' -> 64000, 512 -> 512."""
    if isinstance(value, bool):
        raise ConfigError(f"invalid size: {value!r}")
    if isinstance(value, int):
        return value
    m = _SIZE_RE.match(str(value))
    if not m or m.group(2).lower() not in _UNITS:
        raise ConfigError(f"invalid size: {value!r}")
    return int(m.group(1)) * _UNITS[m.group(2).lower()]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"invalid boolean: {value!r}")


def format_size(n):
    for unit, factor in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if n % factor == 0 and n >= factor:
            return f"{n // factor}{unit}"
    return str(n)
