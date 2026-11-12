"""Version numbers: dot-separated non-negative integers ("1", "2.0", "1.10.3")."""

from functools import total_ordering


@total_ordering
class Version:
    __slots__ = ("text", "parts")

    def __init__(self, text):
        parts = text.split(".")
        if not text or not all(p.isascii() and p.isdigit() for p in parts):
            raise ValueError(f"invalid version {text!r}")
        self.text = text
        self.parts = tuple(int(p) for p in parts)

    @property
    def _key(self):
        parts = list(self.parts)
        while len(parts) > 1 and parts[-1] == 0:
            parts.pop()
        return tuple(parts)

    def __eq__(self, other):
        return isinstance(other, Version) and self._key == other._key

    def __lt__(self, other):
        return self._key < other._key

    def __hash__(self):
        return hash(self._key)

    def __str__(self):
        return self.text

    def __repr__(self):
        return f"Version({self.text!r})"
