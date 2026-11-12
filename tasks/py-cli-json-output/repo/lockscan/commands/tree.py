"""lockscan tree: the dependency tree below the project."""

from lockscan.errors import InvalidLockfile
from lockscan.formatters import text
from lockscan.graph import resolve


def register(sub):
    p = sub.add_parser("tree", help="print the dependency tree")
    p.add_argument("--depth", type=int, default=None, help="maximum depth to show")
    p.set_defaults(run=run)


def build(lock, depth=None):
    if lock.project is None:
        raise InvalidLockfile(f"{lock.path}: no [project] table, nothing to show")
    lines = [lock.project.name]

    def walk(reqs, prefix, level, stack):
        for k, req in enumerate(reqs):
            last = k == len(reqs) - 1
            branch = "`-- " if last else "|-- "
            pkg = resolve(lock, req)
            if pkg is None:
                lines.append(f"{prefix}{branch}{req.name} (missing)")
                continue
            note = " (cycle)" if pkg.label in stack else ""
            lines.append(f"{prefix}{branch}{pkg.label}{note}")
            if note or (depth is not None and level >= depth):
                continue
            walk(pkg.dependencies, prefix + ("    " if last else "|   "), level + 1,
                 stack | {pkg.label})

    walk(lock.project.dependencies, "", 1, frozenset())
    return lines


def run(args, lock):
    print(text.render_tree(build(lock, args.depth)), end="")
    return 0
