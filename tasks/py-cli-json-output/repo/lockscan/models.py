"""In-memory model of a lockfile."""

from dataclasses import dataclass, field

from lockscan.requirements import Requirement
from lockscan.versions import Version


@dataclass
class Package:
    name: str
    version: Version
    source: str = "registry"
    license: str | None = None
    dependencies: list[Requirement] = field(default_factory=list)

    @property
    def label(self):
        return f"{self.name} {self.version}"


@dataclass
class Project:
    name: str
    dependencies: list[Requirement] = field(default_factory=list)


@dataclass
class Lockfile:
    path: str
    packages: list[Package]
    project: Project | None = None

    def by_name(self, name):
        return [p for p in self.packages if p.name == name]

    def names(self):
        seen = {}
        for p in self.packages:
            seen.setdefault(p.name, None)
        return list(seen)

    def direct_names(self):
        if self.project is None:
            return set()
        return {r.name for r in self.project.dependencies}
