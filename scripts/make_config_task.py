"""Generate tasks/read-config-precedence deterministically.

Usage: python3 scripts/make_config_task.py

An exact-answer code-reading task. The repo is `ingestd`, a small event-ingestion service
with a layered configuration system. The prompt fixes the checked-in config files, an
environment and a command line, and asks for the effective `worker.max_batch_bytes`.

Hand derivation of the answer (see the files written below):

  1. defaults.py:                   worker.max_batch_bytes = 1MiB, queue.max_payload_bytes = 4MiB,
                                    queue.envelope_reserve_bytes = 16KiB, worker.batch_align_bytes = 4KiB
  2. config/ingestd.conf:           max_batch_bytes = 2MiB, max_payload_bytes = 6MiB, profile = dev;
                                    its LAST line `@include conf.d/*.conf` pulls in (sorted)
       conf.d/10-limits.conf:       queue.max_payload_bytes = 8MiB, worker.max_batch_bytes = 6MiB
       conf.d/20-sinks.conf:        sink settings only
       (50-legacy.conf.disabled does not match *.conf and is never read)
     -> file layer: max_batch_bytes = 6MiB, max_payload_bytes = 8MiB = 8388608
  3. profile: CLI --profile prod beats INGESTD_PROFILE=staging and service.profile=dev
       config/profiles/prod.conf:   worker.batch_size_kb = 7000 (deprecated key); the new key is
                                    not set in that same layer, so it is translated with
                                    _kb_to_bytes = 7000 * 1000 = 7_000_000 and overrides 6MiB
  4. config/local.conf does not exist (only local.conf.example), so no local layer.
  5. environment:
       INGESTD_PROFILE              reserved (profile selection only)
       INGESTD_WORKER_MAX_BATCH_BYTES=12MiB   single underscore -> not a key, ignored
       INGESTD_QUEUE__ENVELOPE_RESERVE_BYTES=2MiB  canonical name
       INGESTD_ENVELOPE_RESERVE=32KiB              legacy alias, applied after canonical names,
                                                   so it wins -> reserve = 32768
       INGESTD_SINK__COMPRESS=true, INGESTD_LOG_LEVEL=debug  irrelevant
  6. CLI: --set worker.batch_align_bytes=64KiB -> 65536 (power of two, accepted); --workers 6
  7. finalize(): ceiling = 8388608 - 32768 = 8355840; 7_000_000 <= ceiling, no clamp;
                 align down to 65536: 7_000_000 // 65536 = 106 -> 106 * 65536 = 6946816

  ANSWER = 6946816

Plausible wrong answers: 7000000 (no alignment), 6995968 (4KiB alignment), 7168000 (KiB),
6291456 (canonical env name wins, or file value without profile), 3145728 (staging profile),
12582912 (env var taken at face value), 6225920 (include ignored).

The generator writes the repo, then *runs the repo's own loader* in a subprocess with the
stated environment and argv and asserts it yields ANSWER, and also re-runs it with each trap
removed to confirm every trap changes the result.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "read-config-precedence"
ANSWER = 6946816

ENVIRON = {
    "INGESTD_PROFILE": "staging",
    "INGESTD_WORKER_MAX_BATCH_BYTES": "12MiB",
    "INGESTD_QUEUE__ENVELOPE_RESERVE_BYTES": "2MiB",
    "INGESTD_ENVELOPE_RESERVE": "32KiB",
    "INGESTD_SINK__COMPRESS": "true",
    "INGESTD_LOG_LEVEL": "debug",
}
ARGV = ["serve", "--profile", "prod", "--workers", "6", "--set", "worker.batch_align_bytes=64KiB"]

FILES = {}

FILES["README.md"] = """\
# ingestd

`ingestd` accepts batches of JSON events over HTTP, wraps them in queue envelopes and
hands them to a pool of workers that write them to a sink (local files for now).

```
python3 -m ingestd serve                       # uses config/ingestd.conf
python3 -m ingestd serve --profile prod --workers 8
python3 -m ingestd check-config --config path/to/other.conf
```

See docs/configuration.md for how settings are resolved.

Tests: `python3 -m unittest discover -s tests`
"""

FILES["docs/configuration.md"] = """\
# Configuration

Settings are grouped in sections (`service`, `http`, `queue`, `worker`, `sink`, `logging`)
and addressed as `section.name`, e.g. `worker.count`. The full list with defaults is in
`ingestd/config/defaults.py`.

## Layers

Settings are resolved from several layers; a later layer overrides an earlier one:

1. built-in defaults
2. the main config file (`config/ingestd.conf`, or `--config` / `INGESTD_CONFIG`),
   together with any files it `@include`s
3. the profile file `profiles/<profile>.conf` next to the main config file
4. `local.conf` next to the main config file, if present (not checked in)
5. environment variables
6. command-line options

After all layers are merged some values are validated and adjusted; see
`ingestd/config/finalize.py`.

## Config files

INI-like: `[section]` headers and `key = value` lines; `#` and `;` start comments.
`@include <pattern>` reads other files (glob patterns allowed, relative to the including
file) at that point of the file.

## Sizes

Settings ending in `_bytes` accept a plain number of bytes or a number with a unit:
`k`/`KB` (1000), `KiB` (1024), `M`/`MB`, `MiB`, `G`/`GB`, `GiB`.

## Environment variables

`INGESTD_<SECTION>__<NAME>` (double underscore) sets `section.name`, e.g.
`INGESTD_WORKER__COUNT=4`. `INGESTD_CONFIG` and `INGESTD_PROFILE` choose the config file
and profile. A few older names are still accepted for compatibility (see
`ingestd/config/env.py`); setting both an old and a new name logs a warning.

## Deprecated keys

Renamed keys are still read and translated to their new names, with a warning. See
`ingestd/config/deprecations.py`.
"""

FILES["pyproject.toml"] = """\
[project]
name = "ingestd"
version = "2.4.1"
description = "Event ingestion service"
requires-python = ">=3.10"

[project.scripts]
ingestd = "ingestd.cli:main"
"""

FILES["config/ingestd.conf"] = """\
# Main configuration for ingestd. Environment-specific settings live in profiles/.

[service]
name = ingestd
profile = dev
data_dir = ./var

[http]
bind = 0.0.0.0
port = 8040
max_body_bytes = 4MiB
read_timeout_s = 20

[queue]
url = memory://
max_payload_bytes = 6MiB
ack_timeout_s = 30

[worker]
count = 4
max_batch_bytes = 2MiB
max_batch_messages = 1000
flush_interval_ms = 200

[logging]
level = info

# Site-wide limits and sink settings are maintained separately by the platform team.
@include conf.d/*.conf
"""

FILES["config/conf.d/10-limits.conf"] = """\
# Platform limits (managed by platform-infra; do not edit by hand).
# The broker accepts messages up to 8 MiB since the 2024 upgrade.

[queue]
max_payload_bytes = 8MiB

[worker]
max_batch_bytes = 6MiB
"""

FILES["config/conf.d/20-sinks.conf"] = """\
[sink]
kind = file
path = ./var/out
compress = false
"""

FILES["config/conf.d/50-legacy.conf.disabled"] = """\
# Pre-2024 broker limits. Kept for reference; rename to .conf to re-enable.
[queue]
max_payload_bytes = 5MiB
"""

FILES["config/profiles/dev.conf"] = """\
[http]
bind = 127.0.0.1

[worker]
count = 1

[logging]
level = debug
"""

FILES["config/profiles/staging.conf"] = """\
[queue]
url = amqp://mq.staging.internal:5672/ingest

[worker]
count = 4
max_batch_bytes = 3MiB
batch_size_kb = 2500

[logging]
json = true
"""

FILES["config/profiles/prod.conf"] = """\
[queue]
url = amqp://mq.prod.internal:5672/ingest
ack_timeout_s = 60

[worker]
count = 16
# Tuned in INC-4471; keep in sync with the dashboards.
batch_size_kb = 7000
max_batch_messages = 5000

[sink]
compress = true

[logging]
json = true
level = warning
"""

FILES["config/local.conf.example"] = """\
# Copy to config/local.conf for developer overrides (local.conf is git-ignored).
[worker]
count = 1
max_batch_bytes = 16MiB

[logging]
level = debug
"""

FILES[".gitignore"] = """\
__pycache__/
var/
config/local.conf
"""

FILES["ingestd/__init__.py"] = '''\
"""ingestd: HTTP event ingestion service."""

__version__ = "2.4.1"
'''

FILES["ingestd/__main__.py"] = """\
from ingestd.cli import main

raise SystemExit(main())
"""

FILES["ingestd/cli.py"] = '''\
"""Command-line entry point."""

import argparse
import logging
import os
import sys

from ingestd.config import ConfigError, load_settings

log = logging.getLogger(__name__)


def build_parser():
    ap = argparse.ArgumentParser(prog="ingestd")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, help_text in (("serve", "run the service"), ("check-config", "validate config and exit")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--config", help="main config file (default: config/ingestd.conf)")
        p.add_argument("--profile", help="profile name (profiles/<name>.conf)")
        p.add_argument("--workers", type=int, help="shortcut for --set worker.count=N")
        p.add_argument("--port", type=int, help="shortcut for --set http.port=N")
        p.add_argument("--log-level", help="shortcut for --set logging.level=LEVEL")
        p.add_argument(
            "--set",
            dest="overrides",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="override a setting, e.g. --set worker.count=4 (repeatable)",
        )
    return ap


def cli_overrides(args):
    """Turn parsed CLI options into a flat {"section.name": value} layer."""
    layer = {}
    for item in args.overrides:
        key, sep, value = item.partition("=")
        if not sep or "." not in key:
            raise ConfigError(f"--set expects SECTION.NAME=VALUE, got {item!r}")
        layer[key.strip().lower()] = value.strip()
    if args.workers is not None:
        layer["worker.count"] = args.workers
    if args.port is not None:
        layer["http.port"] = args.port
    if args.log_level is not None:
        layer["logging.level"] = args.log_level
    return layer


def main(argv=None, environ=None):
    args = build_parser().parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        settings = load_settings(args, environ)
    except ConfigError as exc:
        print(f"ingestd: configuration error: {exc}", file=sys.stderr)
        return 2
    if args.command == "check-config":
        print("configuration OK")
        return 0
    from ingestd.app import run

    return run(settings)
'''

FILES["ingestd/app.py"] = '''\
"""Wire the components together and run until interrupted."""

import logging
import signal
import threading

from ingestd.http.server import IngestServer
from ingestd.logsetup import configure_logging
from ingestd.metrics import Metrics
from ingestd.queue.client import make_queue
from ingestd.sinks import make_sink
from ingestd.worker.pool import WorkerPool

log = logging.getLogger(__name__)


def run(settings):
    configure_logging(settings["logging"])
    metrics = Metrics()
    queue = make_queue(settings["queue"], metrics)
    sink = make_sink(settings["sink"], settings["service"])
    pool = WorkerPool(settings["worker"], queue, sink, metrics)
    server = IngestServer(settings["http"], queue, metrics)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    log.info("starting %s (profile=%s)", settings["service"]["name"], settings["service"]["profile"])
    pool.start()
    server.start()
    try:
        stop.wait()
    finally:
        server.stop()
        pool.stop()
        sink.close()
    return 0
'''

FILES["ingestd/config/__init__.py"] = '''\
"""Layered configuration. See docs/configuration.md."""

from ingestd.config.errors import ConfigError
from ingestd.config.loader import load_settings

__all__ = ["ConfigError", "load_settings"]
'''

FILES["ingestd/config/errors.py"] = '''\
class ConfigError(Exception):
    """Invalid configuration (bad file, bad value, unknown option)."""
'''

FILES["ingestd/config/defaults.py"] = '''\
"""Built-in defaults. Every valid setting must appear here.

The type of each default decides how values from files, the environment and the command
line are converted: settings whose name ends in `_bytes` are sizes (see units.py).
"""

DEFAULTS = {
    "service": {
        "name": "ingestd",
        "profile": "dev",
        "data_dir": "./var",
    },
    "http": {
        "bind": "127.0.0.1",
        "port": 8040,
        "max_body_bytes": "2MiB",
        "read_timeout_s": 15.0,
    },
    "queue": {
        "url": "memory://",
        "max_payload_bytes": "4MiB",
        "envelope_reserve_bytes": "16KiB",
        "ack_timeout_s": 30.0,
    },
    "worker": {
        "count": 2,
        "max_batch_bytes": "1MiB",
        "max_batch_messages": 500,
        "batch_align_bytes": "4KiB",
        "flush_interval_ms": 250,
    },
    "sink": {
        "kind": "file",
        "path": "./var/out",
        "compress": False,
    },
    "logging": {
        "level": "info",
        "json": False,
    },
}


def known_keys():
    return {f"{section}.{name}" for section, values in DEFAULTS.items() for name in values}
'''

FILES["ingestd/config/units.py"] = '''\
"""Parsing of size and boolean values."""

import re

from ingestd.config.errors import ConfigError

_SIZE_RE = re.compile(r"^\\s*(\\d+)\\s*([A-Za-z]*)\\s*$")
_UNITS = {
    "": 1,
    "b": 1,
    "k": 1000,
    "kb": 1000,
    "kib": 1024,
    "m": 1000**2,
    "mb": 1000**2,
    "mib": 1024**2,
    "g": 1000**3,
    "gb": 1000**3,
    "gib": 1024**3,
}


def parse_size(value):
    """'8MiB' -> 8388608, '64k' -> 64000, 512 -> 512."""
    if isinstance(value, bool):
        raise ConfigError(f"invalid size: {value!r}")
    if isinstance(value, int):
        return value
    m = _SIZE_RE.match(str(value))
    if not m or m.group(2).lower() not in _UNITS:
        raise ConfigError(f"invalid size: {value!r}")
    return int(m.group(1)) * _UNITS[m.group(2).lower()]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"invalid boolean: {value!r}")


def format_size(n):
    for unit, factor in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if n % factor == 0 and n >= factor:
            return f"{n // factor}{unit}"
    return str(n)
'''

FILES["ingestd/config/sources.py"] = '''\
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
'''

FILES["ingestd/config/env.py"] = '''\
"""Settings from environment variables."""

import logging

log = logging.getLogger(__name__)

PREFIX = "INGESTD_"

# Used for choosing files, not settings.
RESERVED = {"INGESTD_CONFIG", "INGESTD_PROFILE"}

# Names from ingestd 1.x, before the INGESTD_<SECTION>__<NAME> scheme.
ENV_ALIASES = {
    "INGESTD_PORT": "http.port",
    "INGESTD_WORKERS": "worker.count",
    "INGESTD_LOG_LEVEL": "logging.level",
    "INGESTD_BATCH_BYTES": "worker.max_batch_bytes",
    "INGESTD_ENVELOPE_RESERVE": "queue.envelope_reserve_bytes",
    "INGESTD_QUEUE_URL": "queue.url",
}


def env_name_to_key(name):
    """INGESTD_WORKER__MAX_BATCH_BYTES -> "worker.max_batch_bytes" (None if not of that form)."""
    if not name.startswith(PREFIX):
        return None
    parts = name[len(PREFIX):].split("__")
    if len(parts) != 2 or not all(parts):
        return None
    return f"{parts[0].lower()}.{parts[1].lower()}"


def env_layer(environ):
    """Return the settings layer for `environ` as a flat {"section.name": str} dict."""
    layer = {}
    for name in sorted(environ):
        if not name.startswith(PREFIX) or name in RESERVED or name in ENV_ALIASES:
            continue
        key = env_name_to_key(name)
        if key is None:
            log.warning("ignoring environment variable %s (expected %s<SECTION>__<NAME>)", name, PREFIX)
            continue
        layer[key] = environ[name]

    # Old names are applied last: deployments that still export them must keep the
    # behaviour they had before the rename, even if a new-style name is also present.
    for old_name, key in ENV_ALIASES.items():
        if old_name in environ:
            if key in layer:
                log.warning("%s overrides the value set for %s", old_name, key)
            layer[key] = environ[old_name]
    return layer
'''

FILES["ingestd/config/deprecations.py"] = '''\
"""Renamed settings that are still accepted."""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


def _kb_to_bytes(value):
    # batch_size_kb predates the size parser. It was always documented as a whole number
    # of kilobytes (1 kB = 1000 bytes); keep that meaning when translating.
    return int(str(value).strip()) * 1000


@dataclass(frozen=True)
class Deprecation:
    new_key: str
    convert: Optional[Callable] = None
    since: str = ""


DEPRECATED = {
    "worker.batch_size_kb": Deprecation("worker.max_batch_bytes", _kb_to_bytes, since="2.0"),
    "queue.reserve_bytes": Deprecation("queue.envelope_reserve_bytes", since="2.1"),
    "http.listen": Deprecation("http.bind", since="1.8"),
    "worker.threads": Deprecation("worker.count", since="1.5"),
}


def translate(layer, source):
    """Rewrite deprecated keys in one layer to their new names.

    If a layer sets both the old and the new key, the new key wins within that layer.
    """
    out = {k: v for k, v in layer.items() if k not in DEPRECATED}
    for old_key, value in layer.items():
        dep = DEPRECATED.get(old_key)
        if dep is None:
            continue
        if dep.new_key in layer:
            log.warning("%s: both %s and %s are set; ignoring %s", source, old_key, dep.new_key, old_key)
            continue
        log.warning("%s: %s is deprecated (since %s), use %s", source, old_key, dep.since, dep.new_key)
        out[dep.new_key] = dep.convert(value) if dep.convert else value
    return out
'''

FILES["ingestd/config/finalize.py"] = '''\
"""Cross-setting validation and adjustments applied after all layers are merged."""

import logging

from ingestd.config.errors import ConfigError

log = logging.getLogger(__name__)

DEFAULT_ALIGN = 4096
LOG_LEVELS = {"debug", "info", "warning", "error"}


def _is_power_of_two(n):
    return n > 0 and n & (n - 1) == 0


def finalize(cfg):
    """Validate and adjust a fully merged, typed settings dict in place."""
    worker, queue, http = cfg["worker"], cfg["queue"], cfg["http"]

    if worker["count"] < 1:
        raise ConfigError("worker.count must be >= 1")
    if not 0 < http["port"] < 65536:
        raise ConfigError("http.port out of range")
    if cfg["logging"]["level"].lower() not in LOG_LEVELS:
        raise ConfigError(f"unknown logging.level {cfg['logging']['level']!r}")
    cfg["logging"]["level"] = cfg["logging"]["level"].lower()

    align = worker["batch_align_bytes"]
    if not _is_power_of_two(align):
        log.warning("worker.batch_align_bytes=%d is not a power of two; using %d", align, DEFAULT_ALIGN)
        align = worker["batch_align_bytes"] = DEFAULT_ALIGN

    # A batch is sent as one queue message, so it must fit in the broker's payload limit
    # after the envelope (headers, routing info, signature) is added.
    if queue["envelope_reserve_bytes"] >= queue["max_payload_bytes"]:
        raise ConfigError("queue.envelope_reserve_bytes must be smaller than queue.max_payload_bytes")
    ceiling = queue["max_payload_bytes"] - queue["envelope_reserve_bytes"]
    if worker["max_batch_bytes"] > ceiling:
        log.info("clamping worker.max_batch_bytes %d -> %d", worker["max_batch_bytes"], ceiling)
        worker["max_batch_bytes"] = ceiling

    # Batches are preallocated in aligned chunks; round down to a whole number of chunks.
    worker["max_batch_bytes"] -= worker["max_batch_bytes"] % align
    if worker["max_batch_bytes"] < align:
        worker["max_batch_bytes"] = align

    if http["max_body_bytes"] < 1024:
        raise ConfigError("http.max_body_bytes must be at least 1KiB")
    return cfg
'''

FILES["ingestd/config/loader.py"] = '''\
"""Merge the configuration layers into one typed settings dict.

Order (later wins): defaults, main config file (+ includes), profile file, local.conf,
environment, command line. Then finalize() validates and adjusts.
"""

import copy
import logging
import os

from ingestd.config import deprecations
from ingestd.config.defaults import DEFAULTS, known_keys
from ingestd.config.env import env_layer
from ingestd.config.errors import ConfigError
from ingestd.config.finalize import finalize
from ingestd.config.sources import read_config_file
from ingestd.config.units import parse_bool, parse_size

log = logging.getLogger(__name__)

DEFAULT_CONFIG = os.path.join("config", "ingestd.conf")


def _coerce(key, raw):
    section, name = key.split(".", 1)
    default = DEFAULTS[section][name]
    if name.endswith("_bytes"):
        return parse_size(raw)
    try:
        if isinstance(default, bool):
            return parse_bool(raw)
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid value for {key}: {raw!r}") from exc
    return str(raw)


def _apply(settings, layer, source):
    valid = known_keys()
    for key, raw in deprecations.translate(layer, source).items():
        if key not in valid:
            log.warning("%s: unknown setting %s ignored", source, key)
            continue
        section, name = key.split(".", 1)
        settings[section][name] = _coerce(key, raw)


def load_settings(args, environ):
    """Build the effective settings for parsed CLI `args` and an `environ` mapping."""
    # Imported here: cli imports this module.
    from ingestd.cli import cli_overrides

    settings = copy.deepcopy(DEFAULTS)
    for section, values in settings.items():
        for name in values:
            settings[section][name] = _coerce(f"{section}.{name}", values[name])

    config_path = args.config or environ.get("INGESTD_CONFIG") or DEFAULT_CONFIG
    _apply(settings, read_config_file(config_path), config_path)
    config_dir = os.path.dirname(os.path.abspath(config_path))

    profile = args.profile or environ.get("INGESTD_PROFILE") or settings["service"]["profile"]
    settings["service"]["profile"] = profile
    profile_path = os.path.join(config_dir, "profiles", f"{profile}.conf")
    if os.path.exists(profile_path):
        _apply(settings, read_config_file(profile_path), profile_path)
    elif args.profile or environ.get("INGESTD_PROFILE"):
        raise ConfigError(f"profile {profile!r} not found ({profile_path})")

    local_path = os.path.join(config_dir, "local.conf")
    if os.path.exists(local_path):
        _apply(settings, read_config_file(local_path), local_path)

    _apply(settings, env_layer(environ), "environment")
    _apply(settings, cli_overrides(args), "command line")
    return finalize(settings)
'''

FILES["ingestd/logsetup.py"] = """\
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "ts": self.formatTime(record),
                "level": record.levelname.lower(),
                "logger": record.name,
                "msg": record.getMessage(),
            }
        )


def configure_logging(cfg):
    handler = logging.StreamHandler(sys.stderr)
    if cfg["json"]:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(cfg["level"].upper())
"""

FILES["ingestd/metrics.py"] = '''\
"""Tiny in-process counters, exposed on GET /metrics."""

import threading
from collections import Counter


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = Counter()

    def incr(self, name, n=1):
        with self._lock:
            self._counters[name] += n

    def snapshot(self):
        with self._lock:
            return dict(self._counters)

    def render(self):
        return "".join(f"ingestd_{k} {v}\\n" for k, v in sorted(self.snapshot().items()))
'''

FILES["ingestd/http/__init__.py"] = ""

FILES["ingestd/http/server.py"] = '''\
"""HTTP front end: POST /v1/events accepts a JSON array of events."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class IngestServer:
    def __init__(self, cfg, queue, metrics):
        self.cfg = cfg
        self.queue = queue
        self.metrics = metrics
        self._httpd = None
        self._thread = None

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            timeout = server.cfg["read_timeout_s"]

            def log_message(self, fmt, *args):  # route through logging
                log.debug("%s - " + fmt, self.address_string(), *args)

            def do_GET(self):
                if self.path == "/healthz":
                    return self._reply(200, b"ok\\n")
                if self.path == "/metrics":
                    return self._reply(200, server.metrics.render().encode())
                return self._reply(404, b"not found\\n")

            def do_POST(self):
                if self.path != "/v1/events":
                    return self._reply(404, b"not found\\n")
                length = int(self.headers.get("Content-Length") or 0)
                if length > server.cfg["max_body_bytes"]:
                    server.metrics.incr("rejected_too_large")
                    return self._reply(413, b"body too large\\n")
                try:
                    events = json.loads(self.rfile.read(length))
                except ValueError:
                    return self._reply(400, b"invalid json\\n")
                if not isinstance(events, list):
                    return self._reply(400, b"expected a JSON array\\n")
                for event in events:
                    server.queue.publish_event(event)
                server.metrics.incr("events_accepted", len(events))
                return self._reply(202, b"accepted\\n")

            def _reply(self, status, body):
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def start(self):
        self._httpd = ThreadingHTTPServer((self.cfg["bind"], self.cfg["port"]), self._handler())
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        log.info("listening on %s:%d", self.cfg["bind"], self.cfg["port"])

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
'''

FILES["ingestd/queue/__init__.py"] = ""

FILES["ingestd/queue/envelope.py"] = '''\
"""Queue message envelopes: routing headers plus an HMAC over the payload."""

import hashlib
import hmac
import json
import time
import uuid

ENVELOPE_VERSION = 3


def wrap(payload: bytes, key: bytes = b"ingestd") -> bytes:
    header = {
        "v": ENVELOPE_VERSION,
        "id": uuid.uuid4().hex,
        "ts": int(time.time() * 1000),
        "len": len(payload),
        "sig": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }
    return json.dumps(header).encode() + b"\\n" + payload


def unwrap(message: bytes, key: bytes = b"ingestd") -> bytes:
    head, _, payload = message.partition(b"\\n")
    header = json.loads(head)
    if header.get("v") != ENVELOPE_VERSION:
        raise ValueError(f"unsupported envelope version {header.get('v')}")
    if len(payload) != header["len"]:
        raise ValueError("truncated message")
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, header["sig"]):
        raise ValueError("bad signature")
    return payload
'''

FILES["ingestd/queue/client.py"] = '''\
"""Queue backends. Only the in-memory backend ships in this repo; AMQP lives in the
deployment image."""

import collections
import json
import logging
import threading

from ingestd.queue.envelope import unwrap, wrap

log = logging.getLogger(__name__)


class MemoryQueue:
    def __init__(self, cfg, metrics):
        self.cfg = cfg
        self.metrics = metrics
        self._events = collections.deque()
        self._batches = collections.deque()
        self._cond = threading.Condition()

    def publish_event(self, event):
        with self._cond:
            self._events.append(event)
            self._cond.notify()

    def take_events(self, max_count, timeout):
        with self._cond:
            if not self._events:
                self._cond.wait(timeout)
            out = []
            while self._events and len(out) < max_count:
                out.append(self._events.popleft())
            return out

    def publish_batch(self, payload: bytes):
        message = wrap(payload)
        if len(message) > self.cfg["max_payload_bytes"]:
            self.metrics.incr("batches_dropped_oversize")
            log.error("dropping batch of %d bytes: over queue.max_payload_bytes", len(message))
            return False
        with self._cond:
            self._batches.append(message)
        self.metrics.incr("batches_published")
        return True

    def drain_batches(self):
        with self._cond:
            items, self._batches = list(self._batches), collections.deque()
        return [json.loads(unwrap(m)) for m in items]


def make_queue(cfg, metrics):
    if cfg["url"].startswith("memory://"):
        return MemoryQueue(cfg, metrics)
    raise RuntimeError(f"queue backend for {cfg['url']!r} is not available in this build")
'''

FILES["ingestd/worker/__init__.py"] = ""

FILES["ingestd/worker/batcher.py"] = '''\
"""Accumulate events into size-bounded batches."""

import json


class Batcher:
    def __init__(self, max_bytes, max_messages):
        self.max_bytes = max_bytes
        self.max_messages = max_messages
        self._items = []
        self._size = 2  # "[]"

    def __len__(self):
        return len(self._items)

    def add(self, event):
        """Add an event; return a full batch (bytes) if this event did not fit."""
        encoded = json.dumps(event, separators=(",", ":")).encode()
        extra = len(encoded) + (1 if self._items else 0)
        if self._items and (
            self._size + extra > self.max_bytes or len(self._items) >= self.max_messages
        ):
            batch = self.flush()
            self._items.append(encoded)
            self._size += len(encoded)
            return batch
        self._items.append(encoded)
        self._size += extra
        return None

    def flush(self):
        if not self._items:
            return None
        batch = b"[" + b",".join(self._items) + b"]"
        self._items = []
        self._size = 2
        return batch
'''

FILES["ingestd/worker/pool.py"] = '''\
"""Worker threads: pull events from the queue, batch them, publish batches to the sink."""

import logging
import threading

from ingestd.worker.batcher import Batcher

log = logging.getLogger(__name__)


class WorkerPool:
    def __init__(self, cfg, queue, sink, metrics):
        self.cfg = cfg
        self.queue = queue
        self.sink = sink
        self.metrics = metrics
        self._stop = threading.Event()
        self._threads = []

    def start(self):
        for i in range(self.cfg["count"]):
            t = threading.Thread(target=self._loop, name=f"worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)

    def _loop(self):
        batcher = Batcher(self.cfg["max_batch_bytes"], self.cfg["max_batch_messages"])
        interval = self.cfg["flush_interval_ms"] / 1000
        while not self._stop.is_set():
            for event in self.queue.take_events(self.cfg["max_batch_messages"], interval):
                full = batcher.add(event)
                if full is not None:
                    self._emit(full)
            if len(batcher):
                self._emit(batcher.flush())
        leftover = batcher.flush()
        if leftover:
            self._emit(leftover)

    def _emit(self, batch):
        try:
            self.sink.write(batch)
            self.metrics.incr("batches_written")
        except OSError:
            log.exception("sink write failed")
            self.metrics.incr("sink_errors")
'''

FILES["ingestd/sinks/__init__.py"] = """\
from ingestd.sinks.file_sink import FileSink


def make_sink(cfg, service_cfg):
    if cfg["kind"] == "file":
        return FileSink(cfg["path"], compress=cfg["compress"])
    raise RuntimeError(f"unknown sink kind {cfg['kind']!r}")
"""

FILES["ingestd/sinks/file_sink.py"] = '''\
"""Write each batch to its own file under a date-partitioned directory."""

import gzip
import os
import threading
import time
import uuid


class FileSink:
    def __init__(self, root, compress=False):
        self.root = root
        self.compress = compress
        self._lock = threading.Lock()

    def write(self, batch: bytes):
        day = time.strftime("%Y/%m/%d", time.gmtime())
        directory = os.path.join(self.root, day)
        os.makedirs(directory, exist_ok=True)
        name = uuid.uuid4().hex + (".json.gz" if self.compress else ".json")
        tmp = os.path.join(directory, "." + name)
        opener = gzip.open if self.compress else open
        with opener(tmp, "wb") as fh:
            fh.write(batch)
        os.replace(tmp, os.path.join(directory, name))

    def close(self):
        pass
'''

FILES["tests/test_units.py"] = """\
import unittest

from ingestd.config.errors import ConfigError
from ingestd.config.units import format_size, parse_bool, parse_size


class SizeTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(parse_size("512"), 512)
        self.assertEqual(parse_size("64k"), 64000)
        self.assertEqual(parse_size("64KiB"), 65536)
        self.assertEqual(parse_size("2MB"), 2000000)
        self.assertEqual(parse_size(" 2 MiB "), 2097152)
        self.assertEqual(parse_size(7), 7)

    def test_invalid(self):
        for bad in ("", "1.5MiB", "12 parsecs", "-1", True):
            with self.assertRaises(ConfigError):
                parse_size(bad)

    def test_format(self):
        self.assertEqual(format_size(8388608), "8MiB")
        self.assertEqual(format_size(1000), "1000")

    def test_bool(self):
        self.assertTrue(parse_bool("Yes"))
        self.assertFalse(parse_bool("off"))


if __name__ == "__main__":
    unittest.main()
"""

FILES["tests/test_batcher.py"] = """\
import json
import unittest

from ingestd.worker.batcher import Batcher


class BatcherTest(unittest.TestCase):
    def test_splits_on_size(self):
        b = Batcher(max_bytes=30, max_messages=100)
        out = [b.add({"n": i}) for i in range(6)]
        full = [x for x in out if x is not None]
        self.assertTrue(full)
        for batch in full:
            self.assertLessEqual(len(batch), 30)
            json.loads(batch)

    def test_splits_on_count(self):
        b = Batcher(max_bytes=10_000, max_messages=2)
        self.assertIsNone(b.add(1))
        self.assertIsNone(b.add(2))
        self.assertEqual(b.add(3), b"[1,2]")
        self.assertEqual(b.flush(), b"[3]")


if __name__ == "__main__":
    unittest.main()
"""

ANSWER_TXT = f"{ANSWER}\n"

CHECK = f"""\
#!/usr/bin/env bash
# Hidden check for read-config-precedence: exact integer, tolerating whitespace and
# backticks.
set -euo pipefail
[ -f ANSWER.txt ] || exit 1
got=$(tr -d '[:space:]`' < ANSWER.txt)
[ "$got" = "{ANSWER}" ]
"""

_env_lines = "\n".join(f"    {k}={v}" for k, v in ENVIRON.items())
TASK_TOML = f'''\
prompt = """
This repository contains `ingestd`, an event-ingestion service with a layered configuration
system. The service is started from the repository root, with the configuration files
exactly as checked in, with these environment variables set (and no other variables whose
names start with INGESTD_):

{_env_lines}

and with this command line:

    python3 -m ingestd {" ".join(ARGV)}

Question: what is the effective value of the setting `worker.max_batch_bytes`, in bytes,
once the service has loaded its configuration (that is, the value the worker pool is
started with)?

Write the answer to a file named ANSWER.txt in the repository root. It must contain only
the integer number of bytes (digits only, e.g. `1048576`). Do not modify any other files.
"""
timeout_s = 900
tags = ["python", "read-codebase", "exact-answer", "config"]
'''


def write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode:
        path.chmod(mode)


PROBE = """\
import json, os, sys
from ingestd.cli import build_parser
from ingestd.config import load_settings
args = build_parser().parse_args(json.loads(sys.argv[1]))
env = json.loads(sys.argv[2])
print(load_settings(args, env)["worker"]["max_batch_bytes"])
"""


def run_loader(repo, environ, argv):
    """Run the repo's own config loader in a fresh interpreter, from the repo root."""
    import json

    proc = subprocess.run(
        [sys.executable, "-c", PROBE, json.dumps(argv), json.dumps(environ)],
        cwd=repo,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=True,
    )
    return int(proc.stdout.strip())


def main():
    for d in ("repo", "solution"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    repo = ROOT / "repo"
    for rel, text in FILES.items():
        write(repo / rel, text)
    write(ROOT / "solution" / "ANSWER.txt", ANSWER_TXT)
    write(ROOT / "check.sh", CHECK, 0o755)
    write(ROOT / "task.toml", TASK_TOML)

    # Prove the answer with the repo's own loader, in a scratch copy (keeps repo/ clean).
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        shutil.copytree(repo, ws)
        got = run_loader(ws, ENVIRON, ARGV)
        assert got == ANSWER, f"loader says {got}, expected {ANSWER}"

        # The repo's own unit tests pass.
        subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ws,
            check=True,
            capture_output=True,
        )

        # Each trap matters: removing it changes the answer.
        def without(key):
            return {k: v for k, v in ENVIRON.items() if k != key}

        variants = {
            "legacy env alias absent": (without("INGESTD_ENVELOPE_RESERVE"), ARGV),
            "no --profile (env staging)": (
                ENVIRON,
                [a for a in ARGV if a not in ("--profile", "prod")],
            ),
            "no alignment override": (ENVIRON, ARGV[:-2]),
        }
        for name, (env, argv) in variants.items():
            alt = run_loader(ws, env, argv)
            assert alt != ANSWER, name
            print(f"  without trap '{name}': {alt}")
        conf = ws / "config" / "ingestd.conf"
        original = conf.read_text()
        conf.write_text(original.replace("@include conf.d/*.conf", ""))
        alt = run_loader(ws, ENVIRON, ARGV)
        assert alt != ANSWER
        print(f"  without the include: {alt}")
        conf.write_text(original)
        (ws / "config" / "local.conf").write_text(
            (ws / "config" / "local.conf.example").read_text()
        )
        alt = run_loader(ws, ENVIRON, ARGV)
        assert alt != ANSWER
        print(f"  if local.conf.example were active: {alt}")

    # repo/ must not contain the answer or anything that writes it.
    for path in repo.rglob("*"):
        if path.is_file():
            assert str(ANSWER) not in path.read_text(), path
    n_files = sum(1 for p in repo.rglob("*") if p.is_file())
    print(f"answer {ANSWER} confirmed by the repo's loader; {n_files} files in repo/")


if __name__ == "__main__":
    main()
