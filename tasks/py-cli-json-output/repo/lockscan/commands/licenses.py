"""lockscan licenses: license overview, optionally failing on a category."""

from lockscan.formatters import text
from lockscan.licenses import CATEGORIES, category, normalize_license
from lockscan.reports import LicenseGroup, LicenseReport


def register(sub):
    p = sub.add_parser("licenses", help="list package licenses")
    p.add_argument("--only-direct", action="store_true",
                   help="only packages the project depends on directly")
    p.add_argument("--fail-on", choices=["copyleft", "unknown"], default=None,
                   help="exit with status 1 if any package is in this category")
    p.set_defaults(run=run)


def build(lock, only_direct=False, fail_on=None):
    direct = lock.direct_names()
    packages = [p for p in lock.packages if not only_direct or p.name in direct]
    counts = {c: 0 for c in CATEGORIES}
    groups = {}
    for pkg in packages:
        lic = normalize_license(pkg.license)
        counts[category(lic)] += 1
        groups.setdefault(lic, []).append(pkg)
    keys = sorted((k for k in groups if k is not None), key=str.lower)
    if None in groups:
        keys.append(None)
    return LicenseReport(
        total=len(packages),
        counts=counts,
        groups=[LicenseGroup(k if k is not None else "(none)", groups[k]) for k in keys],
        only_direct=only_direct,
        fail_on=fail_on,
    )


def run(args, lock):
    report = build(lock, args.only_direct, args.fail_on)
    print(text.render_licenses(report), end="")
    return 1 if report.failed else 0
