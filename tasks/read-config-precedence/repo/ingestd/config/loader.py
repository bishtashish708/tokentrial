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
