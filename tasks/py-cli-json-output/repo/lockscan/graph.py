"""Dependency resolution helpers over a Lockfile."""

from collections import deque


def resolve(lock, requirement):
    """The locked package a requirement resolves to: the highest allowed version, else the
    highest locked version of that name, else None."""
    candidates = lock.by_name(requirement.name)
    if not candidates:
        return None
    allowed = [p for p in candidates if requirement.allows(p.version)]
    return max(allowed or candidates, key=lambda p: p.version)


def reachable_names(lock):
    """Names reachable from the project's dependencies (through every locked version)."""
    if lock.project is None:
        return set()
    seen = set()
    queue = deque(r.name for r in lock.project.dependencies)
    while queue:
        name = queue.popleft()
        if name in seen:
            continue
        seen.add(name)
        for pkg in lock.by_name(name):
            queue.extend(r.name for r in pkg.dependencies)
    return seen


def dependents(lock, name):
    """(who, requirement) pairs that require `name`; `who` is a Package or the Project."""
    out = []
    if lock.project is not None:
        out.extend((lock.project, r) for r in lock.project.dependencies if r.name == name)
    for pkg in lock.packages:
        out.extend((pkg, r) for r in pkg.dependencies if r.name == name)
    return out
