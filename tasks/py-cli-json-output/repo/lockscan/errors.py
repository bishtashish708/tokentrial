"""Errors reported to the user (exit status 2 in text mode)."""


class LockscanError(Exception):
    """Base class. `code` is a stable machine-readable identifier."""

    code = "error"

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ReadError(LockscanError):
    code = "read_error"


class ParseError(LockscanError):
    code = "parse_error"


class InvalidLockfile(LockscanError):
    code = "invalid_lockfile"


class UnknownPackage(LockscanError):
    code = "unknown_package"
