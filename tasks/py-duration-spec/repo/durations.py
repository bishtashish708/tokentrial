"""Human-friendly durations, as used in config files (e.g. `timeout = "1h30m"`)."""


def parse_duration(text: str) -> int:
    """Return the number of seconds in a duration string.

    Specification:
    - A bare non-negative integer is a number of seconds: "90" -> 90.
    - Otherwise the string is one or more parts, each an integer followed by a unit:
      d (86400 s), h (3600 s), m (60 s), s (1 s). Example: "1h30m" -> 5400.
    - Units are case-insensitive: "1H30M" == "1h30m".
    - Leading/trailing whitespace is ignored, and parts may be separated by spaces:
      " 1h 30m " -> 5400. There is no space between a number and its unit ("1 h" is invalid).
    - Each unit may appear at most once, and units must be in descending order
      (d, h, m, s). "30m1h" and "1h1h" are invalid.
    - "0s" and "0" are valid and mean 0.
    Invalid input raises ValueError. This includes: the empty or whitespace-only string,
    unknown units ("5w"), signs ("-5", "+5m"), decimals ("1.5h"), a unit without a number ("h"),
    and a number without a unit after a unit ("1h30").
    """
    raise NotImplementedError


def format_duration(seconds: int) -> str:
    """Format seconds as the shortest canonical duration string.

    Specification:
    - Uses units d, h, m, s in descending order, omitting zero-valued units:
      5400 -> "1h30m", 90061 -> "1d1h1m1s", 3600 -> "1h".
    - 0 -> "0s".
    - Negative numbers or non-integers (including bool) raise ValueError.
    - For every valid duration string t, format_duration(parse_duration(t)) is canonical, and
      parse_duration(format_duration(n)) == n for every n >= 0.
    """
    raise NotImplementedError
