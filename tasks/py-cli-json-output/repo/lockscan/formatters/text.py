"""Human-readable output. Scripts parse some of this, so keep it stable."""

from lockscan.formatters.table import plural, render
from lockscan.licenses import CATEGORIES

_SEVERITY_ORDER = {"error": 0, "warning": 1}


def render_licenses(report):
    title = plural(report.total, "package")
    if report.only_direct:
        title += " (direct dependencies only)"
    lines = [title]
    for cat in CATEGORIES:
        lines.append(f"  {cat:<12}{report.counts[cat]:>4}")
    lines.append("")
    rows = [
        (group.label, ", ".join(p.label for p in group.packages)) for group in report.groups
    ]
    lines.extend(render(rows) or ["no packages"])
    if report.failed:
        lines.append("")
        n = report.counts[report.fail_on]
        lines.append(f"FAILED: {plural(n, report.fail_on + ' package')} found")
    return "\n".join(lines) + "\n"


def render_check(report):
    if not report.issues:
        return "lockscan check: no problems found\n"
    lines = [
        f"lockscan check: {plural(report.errors, 'error')}, {plural(report.warnings, 'warning')}"
    ]
    for issue in sorted(report.issues, key=lambda i: _SEVERITY_ORDER[i.severity]):
        lines.append(f"{issue.severity:<8}{issue.kind:<13}{issue.subject} {issue.detail}".rstrip())
    if report.strict and report.warnings and not report.errors:
        lines.append("(--strict: warnings are failures)")
    return "\n".join(lines) + "\n"


def render_summary(s):
    if s.project is None:
        project = "project: (none)"
    else:
        project = f"project: {s.project} ({plural(s.direct, 'direct dependency')})".replace(
            "dependencys", "dependencies"
        )
    sources = ", ".join(f"{k} {v}" for k, v in sorted(s.sources.items())) or "-"
    return "\n".join([
        project,
        f"packages: {s.packages} ({plural(s.names, 'distinct name')})",
        f"sources: {sources}",
    ]) + "\n"


def render_tree(lines):
    return "\n".join(lines) + "\n"


def render_why(name, entries):
    if not entries:
        return f"{name} is locked but nothing requires it\n"
    lines = [f"{name} is required by:"]
    lines.extend(render([(f"  {who}", f"({req})") for who, req in entries]))
    return "\n".join(lines) + "\n"
