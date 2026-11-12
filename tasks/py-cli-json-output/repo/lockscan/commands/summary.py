"""lockscan summary: counts of packages and sources."""

from collections import Counter

from lockscan.formatters import text
from lockscan.reports import Summary


def register(sub):
    p = sub.add_parser("summary", help="overview of the lockfile")
    p.set_defaults(run=run)


def build(lock):
    return Summary(
        project=lock.project.name if lock.project else None,
        direct=len(lock.project.dependencies) if lock.project else 0,
        packages=len(lock.packages),
        names=len(lock.names()),
        sources=dict(Counter(p.source for p in lock.packages)),
    )


def run(args, lock):
    print(text.render_summary(build(lock)), end="")
    return 0
