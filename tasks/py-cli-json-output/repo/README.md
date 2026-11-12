# lockscan

Reports on a project's dependency lockfile. Standard library only, Python 3.11+.

```
python3 -m lockscan [-f LOCKFILE] COMMAND [options]
```

`LOCKFILE` defaults to `./lockscan.lock`.

| command    | what it does |
|------------|--------------|
| `summary`  | number of packages, distinct names and sources |
| `tree`     | the dependency tree below the project (`--depth N`) |
| `why NAME` | which packages (and the project) require `NAME` |
| `licenses` | license overview; `--only-direct`, `--fail-on {copyleft,unknown}` |
| `check`    | missing / unsatisfied dependencies, duplicate and orphan packages; `--strict` |

Exit status: 0 on success, 1 when `licenses --fail-on` finds a package in that category or
when `check` finds an error (or, with `--strict`, a warning), 2 when the lockfile cannot be
read or is invalid (the message goes to stderr as `lockscan: error: ...`) and for usage
errors.

## Lockfile format

TOML:

```toml
version = 1

[project]                       # optional
name = "shop-api"
dependencies = ["requests>=2.28", "click"]

[[package]]
name = "requests"
version = "2.31.0"
source = "registry"             # registry (default), git or path
license = "Apache-2.0"          # optional
dependencies = ["urllib3 >= 1.21, < 3", "idna"]
```

* Versions are dot-separated non-negative integers; trailing zeros don't matter
  (`1.2` == `1.2.0`).
* A requirement is a package name, optionally followed by comma-separated constraints
  `==`, `!=`, `>=`, `<=`, `>`, `<`. Names are matched exactly (case-sensitive).
* The same name may be locked at several versions; the same name and version only once.

## Checks (`check`)

For every requirement of the project and of every package:

* **missing** (error): no package with that name is locked.
* **unsatisfied** (error): packages with that name are locked, but none of their versions
  satisfies all constraints.

And for the lockfile as a whole:

* **duplicate** (warning): a name is locked at more than one version.
* **orphan** (warning, only when there is a `[project]`): a package whose name is not
  reachable from the project's requirements. Reachability follows requirement names
  through every locked version of a name.

## Licenses (`licenses`)

License strings are normalized by `lockscan.licenses.normalize_license` (known licenses and
aliases map to SPDX-style identifiers, other strings are kept as written but stripped, a
missing or blank license becomes "none") and categorized as permissive, copyleft or
unknown by `lockscan.licenses.category`.

## Development

```
python3 -m unittest discover -s tests
```
