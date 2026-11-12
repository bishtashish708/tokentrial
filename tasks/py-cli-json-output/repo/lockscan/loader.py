"""Reading lockscan.lock files (TOML, see README.md)."""

import tomllib

from lockscan.errors import InvalidLockfile, ParseError, ReadError
from lockscan.models import Lockfile, Package, Project
from lockscan.requirements import parse_requirement
from lockscan.versions import Version

SUPPORTED_VERSIONS = (1,)
SOURCES = ("registry", "git", "path")


def load(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise ReadError(f"cannot read {path}: {e.strerror or e}") from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise ParseError(f"{path}: {e}") from None
    return from_dict(data, path)


def _requirements(items, where, path):
    if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
        raise InvalidLockfile(f"{path}: {where}: dependencies must be a list of strings")
    out = []
    for item in items:
        try:
            out.append(parse_requirement(item))
        except ValueError as e:
            raise InvalidLockfile(f"{path}: {where}: {e}") from None
    return out


def from_dict(data, path="<memory>"):
    if data.get("version") not in SUPPORTED_VERSIONS:
        raise InvalidLockfile(f"{path}: unsupported lockfile version {data.get('version')!r}")

    project = None
    if "project" in data:
        p = data["project"]
        if not isinstance(p, dict) or not isinstance(p.get("name"), str):
            raise InvalidLockfile(f"{path}: [project] needs a name")
        project = Project(p["name"], _requirements(p.get("dependencies", []), "[project]", path))

    packages = []
    seen = set()
    entries = data.get("package", [])
    if not isinstance(entries, list):
        raise InvalidLockfile(f"{path}: 'package' must be an array of tables")
    for n, entry in enumerate(entries, 1):
        where = f"package #{n}"
        if not isinstance(entry, dict):
            raise InvalidLockfile(f"{path}: {where} is not a table")
        name, version = entry.get("name"), entry.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise InvalidLockfile(f"{path}: {where} needs a name and a version")
        try:
            v = Version(version)
        except ValueError as e:
            raise InvalidLockfile(f"{path}: {where}: {e}") from None
        if (name, v) in seen:
            raise InvalidLockfile(f"{path}: {name} {version} is locked twice")
        seen.add((name, v))
        source = entry.get("source", "registry")
        if source not in SOURCES:
            raise InvalidLockfile(f"{path}: {where}: unknown source {source!r}")
        lic = entry.get("license")
        if lic is not None and not isinstance(lic, str):
            raise InvalidLockfile(f"{path}: {where}: license must be a string")
        deps = _requirements(entry.get("dependencies", []), f"{name} {version}", path)
        packages.append(Package(name, v, source, lic, deps))
    return Lockfile(path, packages, project)
