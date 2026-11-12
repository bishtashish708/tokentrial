# JSON output for `licenses` and `check`

Add a `--format {text,json}` option to the `licenses` and `check` subcommands (and only to
those two). It is given after the subcommand name, e.g.
`python3 -m lockscan -f app.lock check --strict --format json`. The default is `text`.

**Text output must stay byte-for-byte unchanged**, with or without `--format text`, for
every command, including exit statuses and error messages.

With `--format json` the command writes exactly one JSON document (an object) to stdout,
followed by a newline, and nothing to stderr. Key order and whitespace inside the document
don't matter. The exit status is the same as in text mode (0 or 1), except for errors
(below). All other options keep their meaning.

Below, "version order" means ascending by version as defined in README.md (numeric per
component, trailing zeros ignored), and a version is always written as the string that
appears in the lockfile.

## `licenses --format json`

```json
{
  "packages": [
    {"name": "requests", "version": "2.31.0", "license": "Apache-2.0",
     "category": "permissive", "direct": true}
  ],
  "counts": {"permissive": 1, "copyleft": 0, "unknown": 0},
  "failed": false
}
```

* `packages`: one object per locked package that the report covers (all packages, or with
  `--only-direct` only those whose name is required directly by the project), sorted by
  `name` (plain string ordering), then by `version` in version order.
  * `license`: the result of `normalize_license` for the package; `null` when the package
    has no license or a blank one.
  * `category`: `"permissive"`, `"copyleft"` or `"unknown"` (as given by `category`; a
    `null` license is `"unknown"`).
  * `direct`: `true` if the project requires the package's name directly; `false`
    otherwise (always `false` when there is no `[project]`).
* `counts`: the number of covered packages per category; all three keys are always present.
* `failed`: `true` if `--fail-on` was given and at least one covered package is in that
  category, else `false`. The exit status is 1 if `failed` is true, else 0.

## `check --format json`

```json
{
  "ok": false,
  "counts": {"errors": 1, "warnings": 1},
  "issues": [
    {"kind": "missing", "severity": "error", "package": "requests", "version": "2.31.0",
     "dependency": "idna", "requirement": "idna>=2", "found": []},
    {"kind": "orphan", "severity": "warning", "package": "six", "version": "1.16.0",
     "dependency": null, "requirement": null, "found": null}
  ]
}
```

Every issue object has exactly these seven keys:

| kind          | severity  | package | version | dependency | requirement | found |
|---------------|-----------|---------|---------|------------|-------------|-------|
| `missing`     | `error`   | requirer name | requirer version, or `null` if the requirer is the project | required name | requirement | `[]` |
| `unsatisfied` | `error`   | requirer name | requirer version, or `null` if the requirer is the project | required name | requirement | locked versions of the required name, in version order |
| `duplicate`   | `warning` | the name | `null` | `null` | `null` | its locked versions, in version order |
| `orphan`      | `warning` | package name | package version | `null` | `null` | `null` |

* "requirer name" is the package's name, or the project's `name` for requirements listed in
  `[project]`. `requirement` is the requirement string as written in the lockfile with
  leading and trailing whitespace removed.
* There is one issue per occurrence, exactly as in the text output (the same set of
  issues). `issues` is sorted by `kind`, then `package`, then `version`, then `dependency`,
  then `requirement`, comparing strings in plain string ordering and putting `null` before
  any string.
* `counts`: number of issues with severity `error` / `warning`.
* `ok`: `true` if the exit status is 0, else `false` (so with `--strict` any warning makes
  it `false`).

## Errors

When the lockfile cannot be read, cannot be parsed, or is invalid, and `--format json` was
given, the command writes to stdout

```json
{"error": {"code": "<code>", "message": "<message>"}}
```

and exits with status **3** (instead of writing `lockscan: error: ...` to stderr and
exiting with 2). `code` is the `code` attribute of the `lockscan.errors` exception class:
`"read_error"` (the file cannot be opened or read, e.g. it does not exist),
`"parse_error"` (not valid UTF-8 TOML) or `"invalid_lockfile"` (valid TOML that breaks the
format rules). `message` is the same message the text mode prints after
`lockscan: error: `.

Command-line usage errors (unknown options, bad choices) are still reported by argparse
as in text mode, regardless of `--format`.
