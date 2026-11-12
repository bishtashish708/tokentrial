"""Generate tasks/py-cron-tz deterministically.

Usage: python3 scripts/make_cron_tz_task.py

Starts from the correct (non-timezone) cronnext module; the agent implements
`next_fire_tz` from SPEC_TZ.md. Hidden cases cluster around real DST transitions.
"""

import json
import random
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from make_cron_task import REFERENCE, SPEC  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "py-cron-tz"

SPEC_TZ = """# Time zones (`next_fire_tz`)

`next_fire_tz(expr, after, tz)`:

- `after` is a timezone-aware `datetime` (any zone). `tz` is an IANA zone name, e.g.
  `"America/New_York"`. The cron expression is evaluated against **local wall-clock time
  in `tz`** using the rules in SPEC.md.
- Returns a timezone-aware `datetime` in **UTC**: the first instant strictly after
  `after` (truncated to the minute) at which the expression fires.
- **Gaps (clocks go forward).** A local time that does not exist on that day (e.g. 02:30
  when clocks jump from 02:00 to 03:00) fires at the first instant after the gap, i.e. the
  instant the clocks jump. If several skipped times match, the expression fires once.
- **Overlaps (clocks go back).** A local time that occurs twice fires only at its **first**
  occurrence.
- Shifts are not always one hour (e.g. `Australia/Lord_Howe` moves 30 minutes).
- If there is no fire time within 366 days after `after`, raise `ValueError`. An unknown
  `tz` raises `ValueError`. A naive `after` raises `ValueError`.
"""

TZ_REFERENCE = """

# --- Time zones (SPEC_TZ.md) ------------------------------------------------------

from datetime import UTC  # noqa: E402
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # noqa: E402


def next_fire_tz(expr: str, after: datetime, tz: str) -> datetime:
    if after.tzinfo is None:
        raise ValueError("after must be timezone-aware")
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"unknown time zone {tz!r}") from e
    parsed = parse(expr)
    minute = timedelta(minutes=1)
    t = after.astimezone(UTC).replace(second=0, microsecond=0) + minute
    limit = after.astimezone(UTC) + timedelta(days=366)
    prev = (t - minute).astimezone(zone).replace(tzinfo=None)
    while t <= limit:
        local = t.astimezone(zone)
        wall = local.replace(tzinfo=None)
        expected = prev + minute
        if wall > expected:  # clocks jumped forward: [expected, wall) never existed
            w = expected
            while w < wall:
                if matches(w, parsed):
                    return t
                w += minute
        if local.fold == 0 and matches(wall, parsed):
            return t
        prev = wall
        t += minute
    raise ValueError("no fire time within 366 days")
"""

STUB = '''

# --- Time zones (SPEC_TZ.md) ------------------------------------------------------


def next_fire_tz(expr: str, after: datetime, tz: str) -> datetime:
    """See SPEC_TZ.md."""
    raise NotImplementedError
'''

VISIBLE = """from datetime import UTC, datetime

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
"""

HIDDEN = """import json
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
"""

CHECK = """#!/usr/bin/env bash
# Hidden check for py-cron-tz: visible tests plus DST reference cases.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m pytest -q -p no:cacheprovider tests >/dev/null 2>&1
"""

TASK_TOML = '''prompt = """
`cronnext` computes when cron expressions fire (SPEC.md). Implement `next_fire_tz` in
cronnext/__init__.py, which evaluates expressions in a time zone, as specified in SPEC_TZ.md.
Do not modify the tests. Run them with `python3 -m pytest tests`. Your implementation will
also be checked against a larger set of cases derived from the specs, including daylight
saving transitions in several time zones.
"""
timeout_s = 1500
requires = ["pytest"]
tags = ["python", "pytest", "spec", "timezones", "hard"]
'''

# (zone, list of transition instants in UTC around which to sample)
ZONES = {
    "America/New_York": ["2026-03-08T07:00", "2026-11-01T06:00"],
    "Europe/London": ["2026-03-29T01:00", "2026-10-25T01:00"],
    "Australia/Lord_Howe": ["2026-04-04T15:00", "2026-10-03T15:30"],
    "America/Sao_Paulo": [],  # no DST: control zone
}
EXPRS = [
    "30 2 * * *",
    "0,30 1-3 * * *",
    "*/20 1,2 * * *",
    "15 1 * * *",
    "45 1 * * SUN",
    "0 2 * * *",
    "*/7 0-3 * * *",
    "30 1 8,9 3 *",
    "0 */2 * * *",
    "59 1 * * *",
    "0 3 * * *",
    "10-50/20 1 * * 0,7",
    "0 0 30 2 *",
]


def main():
    ns: dict = {}
    exec(REFERENCE + TZ_REFERENCE, ns)
    nf = ns["next_fire_tz"]
    rng = random.Random(1789)
    cases = []
    for zone, transitions in ZONES.items():
        anchors = [datetime.fromisoformat(x).replace(tzinfo=UTC) for x in transitions] or [
            datetime(2026, 3, 8, 7, tzinfo=UTC),
            datetime(2026, 11, 1, 6, tzinfo=UTC),
        ]
        for anchor in anchors:
            for expr in EXPRS:
                for _ in range(2):
                    after = anchor - timedelta(minutes=rng.randint(0, 36 * 60))
                    after = after.astimezone(ZoneInfo(rng.choice([zone, "UTC", "Asia/Kolkata"])))
                    try:
                        got = nf(expr, after, zone).isoformat()
                    except ValueError:
                        got = None
                    cases.append([expr, after.isoformat(), zone, got])
    for d in ("repo", "solution", "hidden_tests"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    (ROOT / "repo" / "cronnext").mkdir(parents=True)
    (ROOT / "repo" / "cronnext" / "__init__.py").write_text(REFERENCE + STUB)
    (ROOT / "repo" / "SPEC.md").write_text(SPEC)
    (ROOT / "repo" / "SPEC_TZ.md").write_text(SPEC_TZ)
    (ROOT / "repo" / "tests").mkdir()
    (ROOT / "repo" / "tests" / "test_tz.py").write_text(VISIBLE)
    (ROOT / "solution" / "cronnext").mkdir(parents=True)
    (ROOT / "solution" / "cronnext" / "__init__.py").write_text(REFERENCE + TZ_REFERENCE)
    (ROOT / "hidden_tests").mkdir()
    (ROOT / "hidden_tests" / "test_tz.py").write_text(VISIBLE)
    (ROOT / "hidden_tests" / "test_tz_reference_cases.py").write_text(HIDDEN)
    (ROOT / "hidden_tests" / "tz_cases.json").write_text(json.dumps(cases, indent=0) + "\n")
    (ROOT / "check.sh").write_text(CHECK)
    (ROOT / "check.sh").chmod(0o755)
    (ROOT / "task.toml").write_text(TASK_TOML)
    print(f"{len(cases)} cases, {sum(c[3] is None for c in cases)} expect ValueError")


if __name__ == "__main__":
    main()
