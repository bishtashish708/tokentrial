"""Machine-readable output (SPEC.md)."""

import json

from lockscan.licenses import CATEGORIES, category, normalize_license


def _dump(doc):
    return json.dumps(doc, indent=2) + "\n"


def render_licenses(report):
    packages = sorted(report.packages, key=lambda p: (p.name, p.version))
    out = []
    for pkg in packages:
        lic = normalize_license(pkg.license)
        out.append({
            "name": pkg.name,
            "version": str(pkg.version),
            "license": lic,
            "category": category(lic),
            "direct": pkg.name in report.direct,
        })
    return _dump({
        "packages": out,
        "counts": {c: report.counts[c] for c in CATEGORIES},
        "failed": report.failed,
    })


def _null_first(value):
    return (0, "") if value is None else (1, value)


def render_check(report):
    issues = sorted(
        report.issues,
        key=lambda i: (i.kind, i.package, _null_first(i.version), _null_first(i.dependency),
                       _null_first(i.requirement)),
    )
    return _dump({
        "ok": report.exit_code == 0,
        "counts": {"errors": report.errors, "warnings": report.warnings},
        "issues": [
            {
                "kind": i.kind,
                "severity": i.severity,
                "package": i.package,
                "version": i.version,
                "dependency": i.dependency,
                "requirement": i.requirement,
                "found": i.found,
            }
            for i in issues
        ],
    })


def render_error(err):
    return _dump({"error": {"code": err.code, "message": err.message}})
