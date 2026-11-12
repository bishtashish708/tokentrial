"""Layered configuration. See docs/configuration.md."""

from ingestd.config.errors import ConfigError
from ingestd.config.loader import load_settings

__all__ = ["ConfigError", "load_settings"]
