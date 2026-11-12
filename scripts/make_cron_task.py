"""Generate tasks/py-cron-next deterministically.

Usage: python3 scripts/make_cron_task.py

The repo ships a cron matcher with five semantic bugs. Visible tests cover a few
cases per area; hidden tests compare ~200 seeded random expressions against the
reference implementation, so fixing only what the visible tests show is not enough.
"""

import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "py-cron-next"

SPEC = """# cronnext specification

`next_fire(expr, after)` returns the first minute **strictly after** `after` (a naive
`datetime`; seconds and microseconds are ignored, i.e. truncated) at which the 5-field
cron expression `expr` fires. Fields, separated by whitespace:

| Field        | Values | Names (case-insensitive)        |
|--------------|--------|---------------------------------|
| minute       | 0-59   |                                 |
| hour         | 0-23   |                                 |
| day of month | 1-31   |                                 |
| month        | 1-12   | JAN-DEC                         |
| day of week  | 0-7    | SUN-SAT; both 0 and 7 mean Sunday |

Each field is a comma-separated list of items. An item is `*`, a value `N`, a range
`A-B` (inclusive, A <= B), or any of those followed by a step `/S` (S >= 1). A step on
`*` counts from the field's minimum (`*/15` minutes = 0,15,30,45); a step on a range
counts from the range start (`10-30/7` = 10,17,24); a step on a single value `N/S`
means `N-max/S`.

**Day matching.** If both day-of-month and day-of-week are restricted (neither is `*`),
a day matches when **either** field matches. If only one is restricted, that one must
match. `*/S` counts as restricted.

Days that don't exist in a month (e.g. 31 in April, 30 in February) never match. If no
fire time exists within 10 years after `after`, raise `ValueError`. Malformed expressions
(wrong field count, out-of-range values, A > B, S < 1, unknown names) raise `ValueError`.
"""

REFERENCE = '''"""Cron next-fire calculation. See SPEC.md."""

from datetime import datetime, timedelta

RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
NAMES = [
    {},
    {},
    {},
    {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())},
    {d: i for i, d in enumerate("SUN MON TUE WED THU FRI SAT".split())},
]


def _value(text: str, field: int) -> int:
    names = NAMES[field]
    if text.upper() in names:
        return names[text.upper()]
    if not text.isdigit():
        raise ValueError(f"bad value {text!r}")
    v = int(text)
    lo, hi = RANGES[field]
    if not lo <= v <= hi:
        raise ValueError(f"value {v} out of range")
    return v


def parse_field(text: str, field: int) -> set[int]:
    lo, hi = RANGES[field]
    out: set[int] = set()
    for item in text.split(","):
        base, _, step_s = item.partition("/")
        step = 1
        if step_s:
            if not step_s.isdigit() or int(step_s) < 1:
                raise ValueError(f"bad step in {item!r}")
            step = int(step_s)
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            a_s, b_s = base.split("-", 1)
            a, b = _value(a_s, field), _value(b_s, field)
            if a > b:
                raise ValueError(f"bad range {base!r}")
        else:
            a = _value(base, field)
            b = hi if step_s else a
        out.update(range(a, b + 1, step))
    if field == 4 and 7 in out:
        out.discard(7)
        out.add(0)
    return out


def parse(expr: str):
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [parse_field(p, i) for i, p in enumerate(parts)]
    return sets, parts[2] != "*", parts[4] != "*"


def matches(dt: datetime, parsed) -> bool:
    (mins, hours, doms, months, dows), dom_r, dow_r = parsed
    if dt.minute not in mins or dt.hour not in hours or dt.month not in months:
        return False
    dom_ok = dt.day in doms
    dow_ok = (dt.isoweekday() % 7) in dows
    if dom_r and dow_r:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def next_fire(expr: str, after: datetime) -> datetime:
    parsed = parse(expr)
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = after + timedelta(days=3653)
    # Skip whole days that cannot match, then scan minutes within a matching day.
    while t <= limit:
        day_start = t.replace(hour=0, minute=0)
        if matches(day_start.replace(hour=next(iter(sorted(parsed[0][1]))), minute=next(iter(sorted(parsed[0][0])))), parsed) or _day_ok(t, parsed):
            while t.date() == day_start.date():
                if matches(t, parsed):
                    return t
                t += timedelta(minutes=1)
        else:
            t = day_start + timedelta(days=1)
    raise ValueError("no fire time within 10 years")


def _day_ok(t: datetime, parsed) -> bool:
    (_, _, doms, months, dows), dom_r, dow_r = parsed
    if t.month not in months:
        return False
    dom_ok = t.day in doms
    dow_ok = (t.isoweekday() % 7) in dows
    return (dom_ok or dow_ok) if (dom_r and dow_r) else (dom_ok and dow_ok)
'''

# Five semantic bugs.
BUGGY = (
    REFERENCE
    # 1. names only in upper case
    .replace(
        "    if text.upper() in names:\n        return names[text.upper()]",
        "    if text in names:\n        return names[text]",
    )
    # 2. step on a range counts from the field minimum, not the range start
    .replace(
        "        out.update(range(a, b + 1, step))",
        "        out.update(v for v in range(a, b + 1) if (v - lo) % step == 0)",
    )
    # 3. 7 is not treated as Sunday
    .replace("    if field == 4 and 7 in out:\n        out.discard(7)\n        out.add(0)\n", "")
    # 4. day-of-month / day-of-week always combined with AND
    .replace(
        "    if dom_r and dow_r:\n        return dom_ok or dow_ok\n    return dom_ok and dow_ok",
        "    return dom_ok and dow_ok",
    )
    .replace(
        "    return (dom_ok or dow_ok) if (dom_r and dow_r) else (dom_ok and dow_ok)",
        "    return dom_ok and dow_ok",
    )
    # 5. not strictly after: a matching `after` minute is returned
    .replace(
        "    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)",
        "    t = after.replace(second=0, microsecond=0)",
    )
)
assert BUGGY.count("dom_ok and dow_ok") == 2 and "text in names" in BUGGY

VISIBLE = """from datetime import datetime

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
"""

HIDDEN_HEADER = """import json
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
"""

CHECK = """#!/usr/bin/env bash
# Hidden check for py-cron-next: visible tests plus ~200 reference cases.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m pytest -q -p no:cacheprovider tests >/dev/null 2>&1
"""

TASK_TOML = '''prompt = """
`cronnext.next_fire` computes the next time a cron expression fires, but it has bugs and
its tests fail. SPEC.md defines the required behaviour. Fix cronnext/__init__.py so that
it implements SPEC.md exactly. Do not modify the tests. Run them with `python3 -m pytest tests`.
Your fix will also be checked against a larger set of cases derived from SPEC.md.
"""
timeout_s = 1500
requires = ["pytest"]
tags = ["python", "pytest", "spec", "multi-bug", "hard"]
'''


def random_expr(rng):
    def field(lo, hi, names=None, star_p=0.45):
        r = rng.random()
        if r < star_p:
            return "*" if rng.random() < 0.7 else f"*/{rng.randint(2, max(2, (hi - lo) // 2))}"
        items = []
        for _ in range(rng.randint(1, 2)):
            k = rng.random()
            if k < 0.4:
                v = rng.randint(lo, hi)
                items.append(names[v] if names and v in names and rng.random() < 0.5 else str(v))
            else:
                a = rng.randint(lo, hi - 1)
                b = rng.randint(a, hi)
                s = f"{a}-{b}"
                if rng.random() < 0.5:
                    s += f"/{rng.randint(2, 7)}"
                items.append(s)
        return ",".join(items)

    mon_names = {
        i + 1: n.lower() if rng.random() < 0.5 else n
        for i, n in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())
    }
    dow_names = {
        i: n.capitalize() if rng.random() < 0.5 else n
        for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())
    }
    return " ".join(
        [
            field(0, 59, star_p=0.2),
            field(0, 23, star_p=0.35),
            field(1, 31),
            field(1, 12, mon_names, 0.6),
            field(0, 7, dow_names),
        ]
    )


def main():
    ns: dict = {}
    exec(REFERENCE, ns)
    next_fire = ns["next_fire"]
    rng = random.Random(90210)
    cases = []
    while len(cases) < 200:
        expr = random_expr(rng)
        after = datetime(
            2026,
            rng.randint(1, 12),
            rng.randint(1, 28),
            rng.randint(0, 23),
            rng.randint(0, 59),
            rng.randint(0, 59),
        )
        try:
            got = next_fire(expr, after).isoformat()
        except ValueError:
            got = None
        cases.append([expr, after.isoformat(), got])
    import json

    for d in ("repo", "solution", "hidden_tests"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    (ROOT / "repo" / "cronnext").mkdir(parents=True)
    (ROOT / "repo" / "cronnext" / "__init__.py").write_text(BUGGY)
    (ROOT / "repo" / "SPEC.md").write_text(SPEC)
    (ROOT / "repo" / "tests").mkdir()
    (ROOT / "repo" / "tests" / "test_cronnext.py").write_text(VISIBLE)
    (ROOT / "solution" / "cronnext").mkdir(parents=True)
    (ROOT / "solution" / "cronnext" / "__init__.py").write_text(REFERENCE)
    (ROOT / "hidden_tests").mkdir()
    (ROOT / "hidden_tests" / "test_cronnext.py").write_text(VISIBLE)
    (ROOT / "hidden_tests" / "test_reference_cases.py").write_text(HIDDEN_HEADER)
    (ROOT / "hidden_tests" / "cases.json").write_text(json.dumps(cases, indent=0) + "\n")
    (ROOT / "check.sh").write_text(CHECK)
    (ROOT / "check.sh").chmod(0o755)
    (ROOT / "task.toml").write_text(TASK_TOML)
    print(f"{sum(c[2] is None for c in cases)} of {len(cases)} cases expect ValueError")


if __name__ == "__main__":
    sys.exit(main())
