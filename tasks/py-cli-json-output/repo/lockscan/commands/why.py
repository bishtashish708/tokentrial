"""lockscan why NAME: which packages require NAME."""

from lockscan.errors import UnknownPackage
from lockscan.formatters import text
from lockscan.graph import dependents
from lockscan.models import Project


def register(sub):
    p = sub.add_parser("why", help="show what requires a package")
    p.add_argument("name")
    p.set_defaults(run=run)


def run(args, lock):
    if not lock.by_name(args.name):
        raise UnknownPackage(f"{args.name} is not in {lock.path}")
    entries = []
    for who, req in dependents(lock, args.name):
        label = f"{who.name} (project)" if isinstance(who, Project) else who.label
        entries.append((label, req.text))
    print(text.render_why(args.name, entries), end="")
    return 0
