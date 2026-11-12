# Time zones (`next_fire_tz`)

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
