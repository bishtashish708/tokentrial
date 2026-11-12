# backup rotation

Small shell tooling for the backup host.

- `bin/make-backup.sh PREFIX SRC DIR` – tars SRC into `DIR/PREFIX-YYYYMMDDTHHMMSS.tar.gz`
- `bin/rotate-backups.sh [--dry-run] --config FILE DIR` – keeps the newest KEEP backups
  of every prefix listed in FILE and deletes the rest (exact rules in `SPEC.md`)
- `conf/rotate.conf` – the retention rules used in production

Typical crontab:

```
15 3 * * *  /opt/backup/bin/make-backup.sh db /srv/dumps /var/backups
45 3 * * *  /opt/backup/bin/rotate-backups.sh --config /opt/backup/conf/rotate.conf /var/backups
```

Always try a new config with `--dry-run` first.

Both scripts must keep working with macOS's `/bin/bash` (3.2) and Linux bash 5, using only
POSIX tools (no GNU-only flags). Tests: `bash tests/run-tests.sh`.
