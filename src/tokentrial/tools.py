"""Pinned installs of the tools under test, kept in a local cache.

Nothing here touches the user's global agent configuration: tools are placed in
`~/.cache/tokentrial/tools/` and wired into each run's workspace by the arm
adapters in `arms.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import certifi


def cache_root() -> Path:
    base = os.environ.get("TOKENTRIAL_TOOLS_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(xdg) / "tokentrial" / "tools"


@dataclass(frozen=True)
class Pin:
    name: str
    version: str
    source: str
    commit: str


# Pinned to releases at least two weeks old at the time of pinning (2026-11-11).
RTK = Pin(
    "rtk", "v1.1.0", "https://github.com/rtk-ai/rtk", "753a3b0e939f2e4490fc24e3a1984010f40a103c"
)
CAVEMAN = Pin(
    "caveman",
    "v4.0.1",
    "https://github.com/JuliusBrussee/caveman",
    "d262ab3882952a59312ff3537cd86d894523c5ab",
)
PINS = {p.name: p for p in (RTK, CAVEMAN)}

_RTK_TARGETS = {
    ("Darwin", "arm64"): "aarch64-apple-darwin",
    ("Darwin", "x86_64"): "x86_64-apple-darwin",
    ("Linux", "x86_64"): "x86_64-unknown-linux-musl",
    ("Linux", "aarch64"): "aarch64-unknown-linux-musl",
}


def tool_dir(pin: Pin) -> Path:
    return cache_root() / f"{pin.name}-{pin.version}"


def rtk_bin_dir() -> Path:
    return tool_dir(RTK) / "bin"


def caveman_plugin_dir() -> Path:
    return tool_dir(CAVEMAN) / "src"


def installed(name: str) -> bool:
    return (tool_dir(PINS[name]) / "install.json").exists()


def rtk_asset_name() -> str:
    key = (platform.system(), platform.machine())
    if key not in _RTK_TARGETS:
        raise RuntimeError(f"no pinned rtk build for {key[0]}/{key[1]}")
    return f"rtk-{_RTK_TARGETS[key]}.tar.gz"


def _download(url: str, dest: Path) -> None:
    # Verify TLS against certifi's CA bundle: some Python builds (e.g. python.org on
    # macOS) ship without system CA certificates.
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "tokentrial-installer"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def install_rtk(log=print) -> Path:
    """Download the pinned rtk release binary and verify it against checksums.txt."""
    asset = rtk_asset_name()
    base = f"{RTK.source}/releases/download/{RTK.version}"
    dest = tool_dir(RTK)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log(f"downloading {base}/{asset}")
        _download(f"{base}/{asset}", tmp_path / asset)
        _download(f"{base}/checksums.txt", tmp_path / "checksums.txt")
        digest = hashlib.sha256((tmp_path / asset).read_bytes()).hexdigest()
        expected = {
            line.split()[-1].lstrip("*"): line.split()[0]
            for line in (tmp_path / "checksums.txt").read_text().splitlines()
            if line.strip()
        }
        if expected.get(asset) != digest:
            raise RuntimeError(f"checksum mismatch for {asset}")
        with tarfile.open(tmp_path / asset) as tar:
            tar.extractall(tmp_path / "x", filter="data")
        found = [p for p in (tmp_path / "x").rglob("rtk") if p.is_file()]
        if not found:
            raise RuntimeError(f"no rtk binary inside {asset}")
        shutil.rmtree(dest, ignore_errors=True)
        (dest / "bin").mkdir(parents=True)
        shutil.copy2(found[0], dest / "bin" / "rtk")
        (dest / "bin" / "rtk").chmod(0o755)
    (dest / "install.json").write_text(
        json.dumps({"version": RTK.version, "asset": asset, "sha256": digest}, indent=2) + "\n"
    )
    return dest


def install_caveman(log=print) -> Path:
    """Clone the pinned caveman tag and check it resolves to the pinned commit."""
    dest = tool_dir(CAVEMAN)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    log(f"cloning {CAVEMAN.source} at {CAVEMAN.version}")
    subprocess.run(
        [
            "git",
            "clone",
            "-q",
            "--depth",
            "1",
            "--branch",
            CAVEMAN.version,
            CAVEMAN.source,
            str(dest / "src"),
        ],
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest / "src", capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != CAVEMAN.commit:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(f"caveman {CAVEMAN.version} is {head}, expected {CAVEMAN.commit}")
    (dest / "install.json").write_text(
        json.dumps({"version": CAVEMAN.version, "commit": head}, indent=2) + "\n"
    )
    return dest


INSTALLERS = {"rtk": install_rtk, "caveman": install_caveman}
