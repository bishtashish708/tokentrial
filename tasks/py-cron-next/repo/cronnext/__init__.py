"""Cron next-fire calculation. See SPEC.md."""

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
    if text in names:
        return names[text]
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
        out.update(v for v in range(a, b + 1) if (v - lo) % step == 0)
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
    return dom_ok and dow_ok


def next_fire(expr: str, after: datetime) -> datetime:
    parsed = parse(expr)
    t = after.replace(second=0, microsecond=0)
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
    return dom_ok and dow_ok
