import json
from datetime import datetime
from pathlib import Path

import pytest

from cronnext import next_fire

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


@pytest.mark.parametrize("expr,after,expected", CASES, ids=[c[0] + " @ " + c[1] for c in CASES])
def test_reference_cases(expr, after, expected):
    after_dt = datetime.fromisoformat(after)
    if expected is None:
        with pytest.raises(ValueError):
            next_fire(expr, after_dt)
    else:
        assert next_fire(expr, after_dt) == datetime.fromisoformat(expected)
