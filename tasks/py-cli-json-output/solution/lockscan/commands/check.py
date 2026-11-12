"""lockscan check: consistency problems in the lockfile."""

from lockscan.formatters import jsonfmt, text
from lockscan.graph import reachable_names
from lockscan.reports import CheckReport, Issue


def register(sub):
    p = sub.add_parser("check", help="find missing, unsatisfied, duplicate and orphan packages")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p.add_argument("--format", choices=["text", "json"], default="text", help="output format")
    p.set_defaults(run=run)


def _sorted_versions(packages):
    return [str(p.version) for p in sorted(packages, key=lambda p: p.version)]


def _versions(packages):
    return ", ".join(_sorted_versions(packages))


def find_issues(lock):
    issues = []
    owners = []
    if lock.project is not None:
        owners.append((lock.project.name, lock.project.name, None, lock.project.dependencies))
    owners.extend((pkg.label, pkg.name, str(pkg.version), pkg.dependencies)
                  for pkg in lock.packages)
    for subject, name, version, reqs in owners:
        for req in reqs:
            locked = lock.by_name(req.name)
            fields = dict(package=name, version=version, dependency=req.name,
                          requirement=req.text)
            if not locked:
                issues.append(Issue("error", "missing", subject, f"-> {req.text} (not locked)",
                                    found=[], **fields))
            elif not any(req.allows(p.version) for p in locked):
                issues.append(Issue("error", "unsatisfied", subject,
                                    f"-> {req.text} (locked: {_versions(locked)})",
                                    found=_sorted_versions(locked), **fields))
    for name in lock.names():
        locked = lock.by_name(name)
        if len(locked) > 1:
            issues.append(Issue("warning", "duplicate", name, f"({_versions(locked)})",
                                package=name, found=_sorted_versions(locked)))
    if lock.project is not None:
        reachable = reachable_names(lock)
        for pkg in lock.packages:
            if pkg.name not in reachable:
                issues.append(Issue("warning", "orphan", pkg.label, package=pkg.name,
                                    version=str(pkg.version)))
    return issues


def run(args, lock):
    report = CheckReport(find_issues(lock), strict=args.strict)
    if args.format == "json":
        print(jsonfmt.render_check(report), end="")
    else:
        print(text.render_check(report), end="")
    return report.exit_code
