"""Resolves the audit writer for an event kind from settings.AUDIT_WRITERS."""

from functools import cache
from importlib import import_module

from shopcore import settings


@cache
def writer_for(kind: str):
    path = settings.AUDIT_WRITERS.get(kind) or settings.AUDIT_WRITERS["*"]
    module_name, func_name = path.split(":")
    return getattr(import_module(module_name), func_name)
