from datetime import datetime

import pytest

from cronnext import next_fire

T0 = datetime(2026, 3, 14, 9, 26, 53)  # Saturday


@pytest.mark.parametrize("expr,expected", [
    ("* * * * *", datetime(2026, 3, 14, 9, 27)),
    ("*/15 * * * *", datetime(2026, 3, 14, 9, 30)),
    ("0 12 * * *", datetime(2026, 3, 14, 12, 0)),
    ("0 0 1 * *", datetime(2026, 4, 1, 0, 0)),
    ("30 9 * * MON", datetime(2026, 3, 16, 9, 30)),
    ("0 8 * jan-mar mon-fri", datetime(2026, 3, 16, 8, 0)),
    ("5-40/10 * * * *", datetime(2026, 3, 14, 9, 35)),
    ("0 0 * * 7", datetime(2026, 3, 15, 0, 0)),
    ("0 0 13 * FRI", datetime(2026, 3, 20, 0, 0)),
    ("0 0 31 * *", datetime(2026, 3, 31, 0, 0)),
])
def test_next_fire(expr, expected):
    assert next_fire(expr, T0) == expected


def test_strictly_after():
    assert next_fire("30 9 * * *", datetime(2026, 1, 1, 9, 30)) == datetime(2026, 1, 2, 9, 30)


@pytest.mark.parametrize("expr", ["* * * *", "60 * * * *", "* * * * 8", "5-1 * * * *",
                                  "*/0 * * * *", "* * * FOO *"])
def test_invalid(expr):
    with pytest.raises(ValueError):
        next_fire(expr, T0)


def test_impossible_date():
    with pytest.raises(ValueError):
        next_fire("0 0 30 2 *", T0)
