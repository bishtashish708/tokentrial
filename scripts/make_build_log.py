"""Generate tasks/log-link-failure/repo/build.log deterministically (seeded).

Usage: python3 scripts/make_build_log.py > tasks/log-link-failure/repo/build.log
"""

import random
import sys
from datetime import datetime, timedelta

rng = random.Random(20261111)
t = datetime(2026, 11, 3, 14, 2, 7)
out = []


def emit(line=""):
    global t
    t += timedelta(milliseconds=rng.randint(3, 900))
    out.append(f"{t.isoformat(timespec='milliseconds')}Z {line}")


mods = {
    "core": ["alloc", "arena", "strbuf", "hash", "vec", "log", "time", "config", "error"],
    "net": ["socket", "packet", "frame", "tls_shim", "resolver", "backoff", "http1"],
    "io": ["file", "mmap", "poll", "pipe", "buffer"],
    "codec": ["varint", "base64", "json", "msgpack", "utf8"],
    "util": ["crc32", "sha1", "rand", "bitset", "ring"],
    "legacy": ["compat", "shims"],
    "cli": ["main", "args", "repl", "format"],
}

emit("##[group]Run actions/checkout@v4")
for line in [
    "Syncing repository: acme/wirekit",
    "Getting Git version info",
    "Temporarily overriding HOME='/home/runner/work/_temp/abc' before making global git config changes",
    "Adding repository directory to the temporary git global config as a safe directory",
    "Deleting the contents of '/home/runner/work/wirekit/wirekit'",
    "Initializing the repository",
    "Fetching the repository",
    "HEAD is now at 9c41e2b net: batch packet finalization",
]:
    emit(line)
emit("##[endgroup]")

emit("##[group]Run sudo apt-get install -y build-essential cmake ninja-build python3-pip")
for pkg in [
    "libc6-dev",
    "gcc-13",
    "g++-13",
    "cmake-data",
    "ninja-build",
    "python3-pip",
    "libssl-dev",
    "zlib1g-dev",
    "pkg-config",
    "doxygen",
]:
    for verb in ("Get:", "Unpacking", "Setting up"):
        emit(
            f"{verb} {pkg} ({rng.randint(1, 9)}.{rng.randint(0, 30)}-{rng.randint(1, 5)}ubuntu{rng.randint(1, 3)}) ..."
        )
for i in range(120):
    emit(
        f"Selecting previously unselected package lib{rng.choice(['x', 'gl', 'dbus', 'glib', 'gio', 'ffi', 'pcre'])}{i}."
    )
emit("##[endgroup]")

emit("##[group]Run python3 -m pytest tools/ -q --reruns 2")
emit("============================= test session starts ==============================")
emit("platform linux -- Python 3.12.3, pytest-8.3.2, pluggy-1.5.0")
emit("plugins: rerunfailures-14.0")
emit("collected 64 items")
emit("")
emit("tools/test_codegen.py ........................                               [ 37%]")
emit("tools/test_fetch_fixtures.py R.                                              [ 40%]")
emit("tools/test_versioning.py ......................................              [100%]")
emit("")
emit("=================================== RERUNS ====================================")
emit("_____________________________ test_download_mirror _____________________________")
emit("E   ConnectionResetError: [Errno 104] Connection reset by peer")
emit(
    "ERROR tools/test_fetch_fixtures.py::test_download_mirror - ConnectionResetError (rerun 1 of 2: passed)"
)
emit("======================== 64 passed, 1 rerun in 9.41s ==========================")
emit("##[endgroup]")

emit("##[group]Run cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release")
for line in [
    "-- The C compiler identification is GNU 13.2.0",
    "-- Detecting C compiler ABI info",
    "-- Detecting C compiler ABI info - done",
    "-- Check for working C compiler: /usr/bin/cc - skipped",
    "-- Detecting C compile features",
    "-- Detecting C compile features - done",
    '-- Found OpenSSL: /usr/lib/x86_64-linux-gnu/libcrypto.so (found version "3.0.13")',
    '-- Found ZLIB: /usr/lib/x86_64-linux-gnu/libz.so (found version "1.3")',
    "-- Option WIREKIT_WITH_CRC32_ASM: OFF",
    "-- Option WIREKIT_BUILD_LEGACY: ON (errors in legacy/ are non-fatal)",
    "-- Configuring done (1.8s)",
    "-- Generating done (0.1s)",
    "-- Build files have been written to: /home/runner/work/wirekit/wirekit/build",
]:
    emit(line)
emit("##[endgroup]")

emit("##[group]Run cmake --build build -- -k 0")
objs = [(d, m) for d, ms in mods.items() for m in ms]
# util/crc32 is excluded from the build (see the CMake option above) -> link fails later.
compiled = [(d, m) for d, m in objs if (d, m) != ("util", "crc32")]
n = len(compiled) + 3
step = 0
warn_pool = [
    ("unused variable '{v}'", "-Wunused-variable"),
    (
        "comparison of integer expressions of different signedness: 'int' and 'size_t'",
        "-Wsign-compare",
    ),
    ("'{v}' may be used uninitialized", "-Wmaybe-uninitialized"),
    ("this statement may fall through", "-Wimplicit-fallthrough="),
]
for d, m in compiled:
    step += 1
    emit(f"[{step}/{n}] Building C object src/CMakeFiles/wirekit.dir/{d}/{m}.c.o")
    if (d, m) == ("legacy", "compat"):
        emit("FAILED: src/CMakeFiles/wirekit_legacy.dir/legacy/compat.c.o")
        emit(
            "/usr/bin/cc -DWIREKIT_LEGACY -O2 -c src/legacy/compat.c -o src/CMakeFiles/wirekit_legacy.dir/legacy/compat.c.o"
        )
        emit(
            "src/legacy/compat.c:45:12: error: implicit declaration of function 'gets'; did you mean 'fgets'? [-Wimplicit-function-declaration]"
        )
        emit("   45 |     return gets(buf);")
        emit("      |            ^~~~")
        emit("      |            fgets")
        emit("note: target wirekit_legacy is optional (WIREKIT_BUILD_LEGACY non-fatal); continuing")
        continue
    for _ in range(rng.choice([0, 0, 0, 1, 2])):
        msg, flag = rng.choice(warn_pool)
        v = rng.choice(["len", "rc", "tmp", "cursor", "idx", "flags"])
        line_no = rng.randint(20, 400)
        emit(
            f"src/{d}/{m}.c: In function '{m}_{rng.choice(['init', 'step', 'read', 'write', 'free'])}':"
        )
        emit(f"src/{d}/{m}.c:{line_no}:{rng.randint(5, 30)}: warning: {msg.format(v=v)} [{flag}]")
        emit(f"  {line_no} |     {rng.choice(['size_t', 'int', 'uint8_t'])} {v} = 0;")
emit(f"[{n - 2}/{n}] Linking C static library src/libwirekit.a")
emit(f"[{n - 1}/{n}] Building C object cli/CMakeFiles/wirekit-cli.dir/main.c.o")
emit(f"[{n}/{n}] Linking C executable cli/wirekit-cli")
emit("FAILED: cli/wirekit-cli")
emit(
    ": && /usr/bin/cc -O2 cli/CMakeFiles/wirekit-cli.dir/main.c.o -o cli/wirekit-cli src/libwirekit.a -lssl -lcrypto -lz && :"
)
emit("/usr/bin/ld: src/libwirekit.a(packet.c.o): in function `packet_finalize':")
emit("packet.c:(.text+0x5f3): undefined reference to `crc32_update'")
emit("/usr/bin/ld: src/net/packet.c:212: undefined reference to `crc32_update'")
emit("/usr/bin/ld: src/libwirekit.a(frame.c.o): in function `frame_seal':")
emit("frame.c:(.text+0x1a2): undefined reference to `crc32_finish'")
emit("/usr/bin/ld: src/net/frame.c:88: undefined reference to `crc32_finish'")
emit("collect2: error: ld returned 1 exit status")
emit("ninja: build stopped: cannot make progress due to previous errors.")
emit("##[error]Process completed with exit code 1.")
emit("##[endgroup]")

emit("##[group]Post job cleanup.")
for i in range(400):
    emit(
        f"Cache {rng.choice(['save', 'skip', 'restore'])}: key ccache-{rng.randint(10**6, 10**7)} chunk {i}/400 ({rng.randint(1, 900)} KB)"
    )
emit("Cleaning up orphan processes")
emit("##[endgroup]")

sys.stdout.write("\n".join(out) + "\n")
