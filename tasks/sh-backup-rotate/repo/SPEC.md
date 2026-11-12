# rotate-backups.sh specification

```
bin/rotate-backups.sh [--dry-run] --config FILE DIR
```

Keeps the newest KEEP backups of every configured prefix in directory DIR and deletes the
rest. It must run under bash 3.2 (macOS `/bin/bash`) and bash 4/5 (Linux), using only
POSIX utilities.

## Arguments

Arguments are processed left to right:

- `--dry-run` — report what would be deleted, delete nothing. May be repeated.
- `--config FILE` — the next argument is the config file path, whatever it looks like.
  If `--config` is given more than once, the last one wins. `--config` as the last
  argument is a usage error.
- `--` — every following argument is a non-option argument.
- Any other argument that starts with `-` is an unknown option: usage error.
- Any other argument is a non-option argument.

Exactly one non-option argument (DIR) is required, and `--config` is required.

## Errors and exit codes

Errors are detected in this order; the first one found ends the run:

| Exit | Condition |
|------|-----------|
| 2 | usage error (unknown option, `--config` without a value, missing `--config`, zero or more than one DIR) |
| 3 | config error: FILE is not a readable regular file, or any line of it is invalid (see below) |
| 4 | DIR does not exist or is not a directory |

On any error the script writes nothing to stdout, deletes nothing, writes a one-line
message to stderr and exits with the code above. (The stderr text is not specified.)

## Config file

The file is read line by line; the last line need not end with a newline. Each line is
first stripped of leading and trailing spaces and tabs. Then:

- an empty line, or a line starting with `#`, is ignored;
- otherwise the line is a **rule**: `KEEP`, then one or more spaces/tabs, then `PREFIX`,
  which is the whole rest of the line (internal spaces are part of the prefix, e.g.
  `2 my site` has prefix `my site`).

A rule is invalid (exit 3) if `KEEP` is not 1 to 9 ASCII digits, if there is no
`PREFIX`, if `PREFIX` contains `.` or `/`, or if the same `PREFIX` appears in an earlier
rule. `KEEP` is decimal; leading zeros are allowed and do not mean octal (`08` is 8,
`010` is 10). A config with no rules is valid.

## Which files are backups

Only entries directly inside DIR are considered (no recursion), and only **regular files**:
directories and symbolic links (even links to regular files) are ignored. A file belongs to
the rule with prefix `P` when its name is exactly

```
P-TIMESTAMP[REST]
```

where `TIMESTAMP` is 8 ASCII digits, the letter `T` and 6 ASCII digits
(`YYYYMMDDTHHMMSS`; it is not checked to be a real date) and `REST` is either empty or
starts with `.`. Examples for `P = db`: `db-20250131T235900.sql.gz` and `db-20250131T235900`
belong to `db`; `db-archive-20250131T235900.tar`, `db-20250131T235900-partial.sql`,
`db_20250131T235900.sql` and `db-latest.sql` do not. Because a prefix cannot contain `.`,
a file belongs to at most one rule. Files that belong to no rule are never touched and
never counted. Names never contain newlines but may contain spaces.

## Which files are deleted

For each rule, order its files **newest first by TIMESTAMP** (the timestamp in the name;
modification times are irrelevant). Files with the same TIMESTAMP are ordered by their
full name compared byte by byte (as `LC_ALL=C sort` would), the greater name counting as
newer. The first KEEP files in this order are kept; all the others are deleted. KEEP = 0
deletes every file of that rule; a KEEP larger than the number of files keeps them all.

## Output

Rules are processed in the order they appear in the config file. For each rule, its
deleted files are reported **oldest first** (the reverse of the order above), one line each,
with the bare file name (no directory) printed verbatim:

```
would delete: NAME        (with --dry-run)
deleted: NAME             (without --dry-run; the file is removed)
```

After all rules, exactly one summary line, where K is the total number of kept files and
D the total number of deleted files across all rules:

```
summary: kept K, would delete D     (with --dry-run)
summary: kept K, deleted D          (without --dry-run)
```

Nothing else is written to stdout, and the exit status is 0. With `--dry-run` nothing in
DIR is modified. (If removing a file fails, the script reports it on stderr instead of
printing `deleted:`, does not count it in K or D, carries on, and exits 1.)

### Example

`rotate.conf`:

```
# keep  prefix
3       db
1       db-archive
```

DIR contains `db-20250101T000000.sql`, `db-20250102T000000.sql`, `db-20250103T000000.sql`,
`db-20250104T000000.sql`, `db-archive-20240101T000000.tar`, `db-archive-20240201T000000.tar`
and `notes.txt`. Then `rotate-backups.sh --dry-run --config rotate.conf DIR` prints

```
would delete: db-20250101T000000.sql
would delete: db-archive-20240101T000000.tar
summary: kept 4, would delete 2
```
