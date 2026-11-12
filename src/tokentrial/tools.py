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
    name: str  # install key; also the cache directory prefix
    version: str
    source: str
    commit: str
    tool: str = ""  # upstream tool name when one tool is pinned at several versions

    @property
    def kind(self) -> str:
        return self.tool or self.name


# v0.1/v0.2 pins: releases at least two weeks old when pinned (2026-11-11).
RTK = Pin(
    "rtk", "v1.1.0", "https://github.com/rtk-ai/rtk", "753a3b0e939f2e4490fc24e3a1984010f40a103c"
)
CAVEMAN = Pin(
    "caveman",
    "v4.0.1",
    "https://github.com/JuliusBrussee/caveman",
    "d262ab3882952a59312ff3537cd86d894523c5ab",
)
# v0.3 adds the newer releases (published 2026-11-08, pinned 2026-11-12 at the
# maintainers' latest stable tag) alongside the old ones, for a version comparison.
RTK_V120 = Pin(
    "rtk-v1.2.0",
    "v1.2.0",
    "https://github.com/rtk-ai/rtk",
    "e288a18c04452fd26192f59132e5324a8bb6924d",
    tool="rtk",
)
CAVEMAN_V410 = Pin(
    "caveman-v4.1.0",
    "v4.1.0",
    "https://github.com/JuliusBrussee/caveman",
    "1e91f1306d602d4ca23618701b1185575ae1869b",
    tool="caveman",
)
# headroom: the newest release at least two weeks old (2026-10-26). `commit` is the
# tag's commit; the installed wheel is checked against PyPI's published SHA-256.
HEADROOM = Pin(
    "headroom",
    "0.42.0",
    "https://github.com/headroomlabs-ai/headroom",
    "17d38e5699b7d7c69ac6addcd762f39e42dd7f00",
)
# headroom's documented torch-free "everything" extra (proxy, code-aware compression,
# MCP retrieve server); [all] adds torch-based extras the proxy does not need.
HEADROOM_EXTRAS = "sandbox"
# Shared Python environment for task test suites (put on PATH for every arm equally).
PYTEST = Pin("pytest", "8.4.2", "https://pypi.org/project/pytest/8.4.2/", "")
PINS = {p.name: p for p in (RTK, RTK_V120, CAVEMAN, CAVEMAN_V410, HEADROOM, PYTEST)}

_RTK_TARGETS = {
    ("Darwin", "arm64"): "aarch64-apple-darwin",
    ("Darwin", "x86_64"): "x86_64-apple-darwin",
    ("Linux", "x86_64"): "x86_64-unknown-linux-musl",
    ("Linux", "aarch64"): "aarch64-unknown-linux-musl",
}


def tool_dir(pin: Pin) -> Path:
    return cache_root() / f"{pin.kind}-{pin.version}"


def rtk_bin_dir(pin: Pin = RTK) -> Path:
    return tool_dir(pin) / "bin"


def caveman_plugin_dir(pin: Pin = CAVEMAN) -> Path:
    return tool_dir(pin) / "src"


def headroom_bin() -> Path:
    return tool_dir(HEADROOM) / "venv" / "bin" / "headroom"


def hf_home() -> Path:
    """Model cache for headroom's local compressor, kept with the pinned install."""
    return tool_dir(HEADROOM) / "hf"


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


def install_rtk(log=print, pin: Pin = RTK) -> Path:
    """Download the pinned rtk release binary and verify it against checksums.txt."""
    asset = rtk_asset_name()
    base = f"{pin.source}/releases/download/{pin.version}"
    dest = tool_dir(pin)
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
        json.dumps({"version": pin.version, "asset": asset, "sha256": digest}, indent=2) + "\n"
    )
    return dest


def install_caveman(log=print, pin: Pin = CAVEMAN) -> Path:
    """Clone the pinned caveman tag and check it resolves to the pinned commit."""
    dest = tool_dir(pin)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    log(f"cloning {pin.source} at {pin.version}")
    subprocess.run(
        [
            "git",
            "clone",
            "-q",
            "--depth",
            "1",
            "--branch",
            pin.version,
            pin.source,
            str(dest / "src"),
        ],
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest / "src", capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != pin.commit:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(f"caveman {pin.version} is {head}, expected {pin.commit}")
    (dest / "install.json").write_text(
        json.dumps({"version": pin.version, "commit": head}, indent=2) + "\n"
    )
    return dest


def task_env_bin() -> Path:
    return tool_dir(PYTEST) / "venv" / "bin"


def install_task_env(log=print) -> Path:
    """A venv with pinned pytest for tasks whose tests use pytest."""
    dest = tool_dir(PYTEST)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    log(f"creating venv with pytest=={PYTEST.version}")
    subprocess.run(["uv", "venv", "-q", "--python", "python3", str(dest / "venv")], check=True)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "-q",
            "--python",
            str(dest / "venv" / "bin" / "python"),
            f"pytest=={PYTEST.version}",
        ],
        check=True,
    )
    version = subprocess.run(
        [str(task_env_bin() / "pytest"), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (dest / "install.json").write_text(json.dumps({"version": PYTEST.version, "check": version}))
    return dest


def _headroom_wheel_tag() -> str:
    key = (platform.system(), platform.machine())
    tags = {
        ("Darwin", "arm64"): "macosx_11_0_arm64",
        ("Darwin", "x86_64"): "macosx_10_12_x86_64",
        ("Linux", "x86_64"): "manylinux_2_28_x86_64",
        ("Linux", "aarch64"): "manylinux_2_28_aarch64",
    }
    if key not in tags:
        raise RuntimeError(f"no pinned headroom wheel for {key[0]}/{key[1]}")
    return tags[key]


def install_headroom(log=print, pin: Pin = HEADROOM) -> Path:
    """Install the pinned headroom wheel into its own venv.

    The wheel is downloaded from PyPI and its SHA-256 checked against both PyPI's
    published digest and the same-named asset of the GitHub release. Dependencies are
    resolved by uv from PyPI; the resolved versions are recorded in install.json.
    The local compressor model is fetched once here (into the pinned install's own
    cache), so benchmark runs do not download anything.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    meta_url = f"https://pypi.org/pypi/headroom-ai/{pin.version}/json"
    req = urllib.request.Request(meta_url, headers={"User-Agent": "tokentrial-installer"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        meta = json.load(resp)
    tag = _headroom_wheel_tag()
    files = [u for u in meta["urls"] if u["filename"].endswith(f"{tag}.whl")]
    if len(files) != 1:
        raise RuntimeError(f"expected one headroom {pin.version} wheel for {tag}, got {files}")
    wheel = files[0]
    dest = tool_dir(pin)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / wheel["filename"]
        log(f"downloading {wheel['url']}")
        _download(wheel["url"], path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != wheel["digests"]["sha256"]:
            raise RuntimeError(f"PyPI digest mismatch for {wheel['filename']}")
        gh = Path(tmp) / "github.whl"
        _download(f"{pin.source}/releases/download/v{pin.version}/{wheel['filename']}", gh)
        if hashlib.sha256(gh.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"GitHub release asset differs from PyPI for {wheel['filename']}")
        venv = dest / "venv"
        log(f"creating venv with headroom-ai[{HEADROOM_EXTRAS}]=={pin.version}")
        subprocess.run(["uv", "venv", "-q", "--python", "3.13", str(venv)], check=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "-q",
                "--python",
                str(venv / "bin" / "python"),
                f"headroom-ai[{HEADROOM_EXTRAS}] @ {path.as_uri()}",
            ],
            check=True,
        )
    freeze = subprocess.run(
        ["uv", "pip", "freeze", "--python", str(dest / "venv" / "bin" / "python")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    log("warming the local compressor model cache")
    warm = subprocess.run(
        [
            str(dest / "venv" / "bin" / "python"),
            "-I",
            str(Path(__file__).parent / "data" / "headroom_warmup.py"),
        ],
        env={**_headroom_env(dest / "home"), "PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=900,
    )
    if warm.returncode != 0:
        raise RuntimeError(f"headroom warm-up failed: {(warm.stderr or warm.stdout)[-500:]}")
    log(warm.stdout.strip().splitlines()[-1] if warm.stdout.strip() else "warm-up done")
    shutil.rmtree(dest / "home", ignore_errors=True)
    (dest / "install.json").write_text(
        json.dumps(
            {
                "version": pin.version,
                "commit": pin.commit,
                "wheel": wheel["filename"],
                "sha256": digest,
                "extras": HEADROOM_EXTRAS,
                "packages": freeze,
            },
            indent=2,
        )
        + "\n"
    )
    return dest


def _headroom_env(home: Path) -> dict[str, str]:
    """Environment for every headroom process: no telemetry, state kept out of real HOME."""
    home.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(home),
        "HEADROOM_CONFIG_DIR": str(home / ".headroom"),
        "HEADROOM_WORKSPACE_DIR": str(home / ".headroom"),
        "HEADROOM_SAVINGS_PATH": str(home / ".headroom" / "proxy_savings.json"),
        "HF_HOME": str(hf_home()),
        "HEADROOM_TELEMETRY": "off",
        "HEADROOM_BEACON": "off",
        "DO_NOT_TRACK": "1",
    }


headroom_env = _headroom_env

INSTALLERS = {
    "rtk": install_rtk,
    "rtk-v1.2.0": lambda log=print: install_rtk(log, RTK_V120),
    "caveman": install_caveman,
    "caveman-v4.1.0": lambda log=print: install_caveman(log, CAVEMAN_V410),
    "headroom": install_headroom,
    "pytest": install_task_env,
}
