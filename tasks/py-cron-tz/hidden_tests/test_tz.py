from datetime import UTC, datetime

import pytest

from cronnext import next_fire_tz

NY = "America/New_York"


def u(*a):
    return datetime(*a, tzinfo=UTC)


def test_plain_day():
    # 2026-06-01 09:00 EDT = 13:00 UTC
    assert next_fire_tz("0 9 * * *", u(2026, 6, 1, 12, 0), NY) == u(2026, 6, 1, 13, 0)


def test_gap_fires_when_clocks_jump():
    # 2026-03-08 02:30 does not exist in New York; clocks jump 02:00 EST -> 03:00 EDT (07:00 UTC)
    assert next_fire_tz("30 2 * * *", u(2026, 3, 8, 5, 0), NY) == u(2026, 3, 8, 7, 0)


def test_overlap_fires_once():
    # 2026-11-01 01:30 happens twice in New York; fire only at the first (EDT, 05:30 UTC)
    first = next_fire_tz("30 1 * * *", u(2026, 11, 1, 4, 0), NY)
    assert first == u(2026, 11, 1, 5, 30)
    assert next_fire_tz("30 1 * * *", first, NY) == u(2026, 11, 2, 6, 30)


def test_returns_utc():
    assert next_fire_tz("0 0 * * *", u(2026, 1, 1), "Asia/Tokyo").tzinfo == UTC


@pytest.mark.parametrize("args", [("* * * * *", datetime(2026, 1, 1), NY),
                                  ("* * * * *", u(2026, 1, 1), "Mars/Olympus")])
def test_invalid(args):
    with pytest.raises(ValueError):
        next_fire_tz(*args)
