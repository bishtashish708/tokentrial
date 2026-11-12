"""License names and categories."""

PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "PSF-2.0", "Unlicense"}
COPYLEFT = {"GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "MPL-2.0"}
CATEGORIES = ("permissive", "copyleft", "unknown")

_ALIASES = {
    "mit license": "MIT",
    "apache 2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "new bsd": "BSD-3-Clause",
    "simplified bsd": "BSD-2-Clause",
    "python software foundation license": "PSF-2.0",
    "gplv2": "GPL-2.0",
    "gplv3": "GPL-3.0",
    "lgplv3": "LGPL-3.0",
    "mozilla public license 2.0": "MPL-2.0",
}
_CANONICAL = {name.lower(): name for name in PERMISSIVE | COPYLEFT}


def normalize_license(raw):
    """Canonical identifier for a license string.

    Known licenses (case-insensitive, including the aliases above) map to their SPDX-style
    identifier; other non-blank strings are returned stripped; missing or blank -> None.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    key = s.lower()
    return _CANONICAL.get(key) or _ALIASES.get(key) or s


def category(license_id):
    if license_id in PERMISSIVE:
        return "permissive"
    if license_id in COPYLEFT:
        return "copyleft"
    return "unknown"
