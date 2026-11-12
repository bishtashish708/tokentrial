"""Drive the Claude Code CLI headlessly and parse its stream-json output."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field

from tokentrial.pricing import Price, Usage, add_usage, cost_breakdown, usage_from_api

# Tools the agent may use. Enough to read, edit, and run tests; no web, no MCP.
ALLOWED_TOOLS = "Read,Edit,Write,Glob,Grep,Bash"

# Environment variables that would make Claude Code bill an API account instead
# of the logged-in subscription.
API_CREDENTIAL_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

_LIMIT_RE = re.compile(
    r"usage limit|rate[ _-]?limit|hit your limit|limit reached|limit will reset|"
    r"\b429\b|overloaded",
    re.IGNORECASE,
)
_RESET_EPOCH_RE = re.compile(r"\|(\d{10})\b")


class UsageLimitReached(RuntimeError):
    """Claude Code reported a subscription usage limit or rate limit."""

    def __init__(self, message: str, reset_epoch: int | None = None):
        super().__init__(message)
        self.reset_epoch = reset_epoch


def looks_like_usage_limit(text: str) -> bool:
    return bool(text) and bool(_LIMIT_RE.search(text))


def parse_reset_epoch(text: str) -> int | None:
    m = _RESET_EPOCH_RE.search(text or "")
    return int(m.group(1)) if m else None


def build_command(claude_bin: list[str], model: str) -> list[str]:
    """Headless invocation. The prompt is sent on stdin.

    User-level settings, MCP servers, and slash commands are excluded so every
    arm starts from the same Claude Code configuration; only the workspace's
    own project settings (where an arm may install itself) apply.
    """
    return [
        *claude_bin,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
    ]


def child_env(mode: str) -> dict[str, str]:
    env = dict(os.environ)
    if mode == "subscription":
        for var in API_CREDENTIAL_VARS:
            env.pop(var, None)
    return env


def auth_status(claude_bin: list[str]) -> dict:
    """`claude auth status --json`. Makes no model call."""
    out = subprocess.run(
        [*claude_bin, "auth", "status", "--json"], capture_output=True, text=True, timeout=30
    )
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"loggedIn": False, "error": (out.stderr or out.stdout).strip()[:300]}


@dataclass
class StreamResult:
    """What one Claude Code session consumed and how it ended."""

    calls: dict[str, Usage] = field(default_factory=dict)  # message id -> usage
    result: dict | None = None
    init: dict | None = None

    @property
    def usage(self) -> Usage:
        total = Usage()
        for u in self.calls.values():
            total = add_usage(total, u)
        if not self.calls and self.result and self.result.get("usage"):
            # Fallback when per-call usage is missing: session totals.
            return usage_from_api(self.result["usage"])
        return total


class StreamParser:
    """Incrementally parse stream-json lines; report the cost added by each line.

    Claude Code may emit several `assistant` events for one API response (one per
    content block), each repeating that response's usage. Usage is therefore
    keyed by message id and only the change in cost is reported.
    """

    def __init__(self, price: Price):
        self.price = price
        self.state = StreamResult()
        self._cost_by_id: dict[str, float] = {}

    def feed(self, line: str) -> float:
        line = line.strip()
        if not line:
            return 0.0
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if looks_like_usage_limit(line):
                raise UsageLimitReached(line[:300], parse_reset_epoch(line)) from None
            return 0.0

        etype = event.get("type")
        if etype == "system" and event.get("subtype") == "init":
            self.state.init = {
                k: event.get(k)
                for k in ("model", "claude_code_version", "tools", "mcp_servers", "cwd")
            }
        elif etype == "assistant":
            msg = event.get("message") or {}
            mid, raw = msg.get("id"), msg.get("usage")
            if mid and raw:
                usage = usage_from_api(raw)
                self.state.calls[mid] = usage
                new = cost_breakdown(usage, self.price)["total"]
                delta = new - self._cost_by_id.get(mid, 0.0)
                self._cost_by_id[mid] = new
                return max(delta, 0.0)
            text = _assistant_text(msg)
            if event.get("error") and looks_like_usage_limit(text):
                raise UsageLimitReached(text[:300], parse_reset_epoch(text))
        elif etype == "result":
            self.state.result = event
            text = str(event.get("result") or "")
            if event.get("is_error") and looks_like_usage_limit(text):
                raise UsageLimitReached(text[:300], parse_reset_epoch(text))
        return 0.0


def _assistant_text(msg: dict) -> str:
    parts = msg.get("content") or []
    return " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
