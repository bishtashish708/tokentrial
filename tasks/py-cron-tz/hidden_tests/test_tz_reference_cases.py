import json
from datetime import datetime
from pathlib import Path

import pytest

from cronnext import next_fire_tz

CASES = json.loads((Path(__file__).parent / "tz_cases.json").read_text())


@pytest.mark.parametrize("expr,after,tz,expected", CASES,
                         ids=[f"{c[2]} {c[0]} @ {c[1]}" for c in CASES])
def test_tz_reference_cases(expr, after, tz, expected):
    after_dt = datetime.fromisoformat(after)
    if expected is None:
        with pytest.raises(ValueError):
            next_fire_tz(expr, after_dt, tz)
    else:
        assert next_fire_tz(expr, after_dt, tz) == datetime.fromisoformat(expected)
