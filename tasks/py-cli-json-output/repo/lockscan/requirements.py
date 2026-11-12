"""Requirement strings: a package name optionally followed by constraints.

    name
    name>=1.2
    name >= 1.2, <2, != 1.5.1
"""

import operator
import re

from lockscan.versions import Version

_NAME = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)\Z", re.S)
_CONSTRAINT = re.compile(r"(==|!=|>=|<=|>|<)\s*(\S+)\Z")
_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}


class Requirement:
    def __init__(self, text, name, constraints):
        self.text = text
        self.name = name
        self.constraints = constraints  # list of (op, Version)

    def allows(self, version):
        return all(_OPS[op](version, bound) for op, bound in self.constraints)

    def __repr__(self):
        return f"Requirement({self.text!r})"


def parse_requirement(text):
    """Parse a requirement string; raises ValueError if malformed."""
    stripped = text.strip()
    m = _NAME.match(stripped)
    if not m:
        raise ValueError(f"invalid requirement {text!r}")
    name, rest = m.group(1), m.group(2).strip()
    constraints = []
    if rest:
        for item in rest.split(","):
            c = _CONSTRAINT.match(item.strip())
            if not c:
                raise ValueError(f"invalid requirement {text!r}")
            constraints.append((c.group(1), Version(c.group(2))))
    return Requirement(stripped, name, constraints)
