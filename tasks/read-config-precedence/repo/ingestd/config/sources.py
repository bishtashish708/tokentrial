"""Reading INI-like config files with @include support."""

import glob
import os

from ingestd.config.errors import ConfigError

MAX_INCLUDE_DEPTH = 8


def read_config_file(path, _depth=0):
    """Return the settings in `path` (and its includes) as an ordered flat dict.

    Keys are "section.name". Later assignments override earlier ones, including those
    made by included files: an `@include` is expanded in place, at the line where it
    appears.
    """
    if _depth > MAX_INCLUDE_DEPTH:
        raise ConfigError(f"@include nested too deeply at {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc

    base = os.path.dirname(os.path.abspath(path))
    values = {}
    section = None
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("@include"):
            pattern = line[len("@include"):].strip()
            if not pattern:
                raise ConfigError(f"{path}:{lineno}: @include needs a path")
            full = os.path.join(base, pattern)
            matches = sorted(glob.glob(full))
            if not matches and not glob.has_magic(pattern):
                raise ConfigError(f"{path}:{lineno}: included file not found: {pattern}")
            for included in matches:
                values.update(read_config_file(included, _depth + 1))
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ConfigError(f"{path}:{lineno}: expected key = value")
        if section is None:
            raise ConfigError(f"{path}:{lineno}: setting outside of a [section]")
        value = value.split(" #", 1)[0].strip()
        values[f"{section}.{key.strip().lower()}"] = value
    return values
