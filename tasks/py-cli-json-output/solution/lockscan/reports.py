"""Report objects built by the commands and rendered by the formatters."""

from dataclasses import dataclass, field

from lockscan.models import Package


@dataclass
class LicenseGroup:
    label: str  # normalized license, or "(none)"
    packages: list[Package]


@dataclass
class LicenseReport:
    total: int
    counts: dict[str, int]
    groups: list[LicenseGroup]
    only_direct: bool = False
    fail_on: str | None = None
    packages: list[Package] = field(default_factory=list)  # covered packages
    direct: set[str] = field(default_factory=set)  # names the project requires directly

    @property
    def failed(self):
        return self.fail_on is not None and self.counts[self.fail_on] > 0


@dataclass
class Issue:
    severity: str  # "error" or "warning"
    kind: str  # "missing", "unsatisfied", "duplicate", "orphan"
    subject: str  # what the issue is about, as shown to the user
    detail: str = ""
    # structured fields (JSON output)
    package: str = ""
    version: str | None = None
    dependency: str | None = None
    requirement: str | None = None
    found: list[str] | None = None


@dataclass
class CheckReport:
    issues: list[Issue] = field(default_factory=list)
    strict: bool = False

    @property
    def errors(self):
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warnings(self):
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def exit_code(self):
        if self.errors or (self.strict and self.warnings):
            return 1
        return 0


@dataclass
class Summary:
    project: str | None
    direct: int
    packages: int
    names: int
    sources: dict[str, int]
