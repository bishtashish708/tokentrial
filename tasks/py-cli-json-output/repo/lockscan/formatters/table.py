"""Two-column plain-text tables."""


def render(rows, gap=2):
    """rows: list of (left, right) strings. Returns a list of lines."""
    if not rows:
        return []
    width = max(len(left) for left, _ in rows) + gap
    return [f"{left:<{width}}{right}".rstrip() for left, right in rows]


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")
