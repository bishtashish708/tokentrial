"""JSON Lines reading and writing."""

import json

REQUIRED = ("id", "name", "email", "phone", "updated", "tags")


class InputError(ValueError):
    pass


def read_records(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise InputError(f"{path}:{lineno}: invalid JSON: {e}") from None
            missing = [k for k in REQUIRED if k not in rec]
            if missing:
                raise InputError(f"{path}:{lineno}: missing keys {', '.join(missing)}")
            records.append(rec)
    return records


def write_records(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")
