# cronnext specification

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
