"""Drive the Claude Code CLI headlessly and parse its stream-json output."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field

from tokentrial.pricing import (
    Price,
    Usage,
    add_usage,
    cost_breakdown,
    price_for_call,
    tiered_cost,
    usage_from_api,
)

# Tools the agent may use. Enough to read, edit, and run tests; no web, no MCP.
ALLOWED_TOOLS = "Read,Edit,Write,Glob,Grep,Bash"

# Environment variables that would make Claude Code bill an API account instead
# of the logged-in subscription.
API_CREDENTIAL_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

# Host variables kept in the agent's environment. Every other CLAUDE*/ANTHROPIC*
# variable is dropped: when tokentrial itself runs inside a Claude Code session
# (terminal, IDE, desktop app), inherited variables such as ANTHROPIC_BASE_URL or
# CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH make the nested agent use the host's
# proxy and auth path, which fails, and would make arms depend on the host.
KEEP_HOST_VARS = ("CLAUDE_CONFIG_DIR",)

# Variables set for every agent run.
AGENT_ENV = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}

_LIMIT_RE = re.compile(
    r"usage limit|rate[ _-]?limit|hit your limit|limit reached|limit will reset|"
    r"\b429\b|overloaded",
    re.IGNORECASE,
)
_RESET_EPOCH_RE = re.compile(r"\|(\d{10})\b")


class AgentFatalError(RuntimeError):
    """An error no retry will fix (e.g. authentication); stop the experiment."""


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


def build_command(
    claude_bin: list[str],
    model: str,
    extra_args: list[str] | None = None,
    extra_allowed: list[str] | None = None,
) -> list[str]:
    """Headless invocation. The prompt is sent on stdin.

    User-level settings, MCP servers, and slash commands are excluded so every
    arm starts from the same Claude Code configuration; only the workspace's
    own project settings (where an arm may install itself) apply. `extra_allowed`
    pre-approves tools an arm brings itself (e.g. its own MCP server's tools).
    """
    allowed = ",".join([ALLOWED_TOOLS, *(extra_allowed or [])])
    return [
        *claude_bin,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        # Log hook activity (no effect on the agent's context): evidence that a tool
        # arm's hooks actually fired.
        "--include-hook-events",
        "--model",
        model,
        "--permission-mode",
        "dontAsk",
        "--tools",
        ALLOWED_TOOLS,
        "--allowedTools",
        allowed,
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
        *(extra_args or []),
    ]


def child_env(mode: str) -> dict[str, str]:
    keep = set(KEEP_HOST_VARS)
    if mode == "api":
        keep.add("ANTHROPIC_API_KEY")
    env = {
        k: v
        for k, v in os.environ.items()
        if k in keep or not (k.startswith("CLAUDE") or k.startswith("ANTHROPIC"))
    }
    env.update(AGENT_ENV)
    return env


def _is_auth_failure(text: str, error: str | None = None) -> bool:
    return error == "authentication_failed" or "failed to authenticate" in (text or "").lower()


def auth_status(claude_bin: list[str], mode: str = "subscription") -> dict:
    """`claude auth status --json` in the agent's environment. Makes no model call."""
    out = subprocess.run(
        [*claude_bin, "auth", "status", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        env=child_env(mode),
    )
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"loggedIn": False, "error": (out.stderr or out.stdout).strip()[:300]}


@dataclass
class StreamResult:
    """What one Claude Code session consumed and how it ended."""

    calls: dict[str, Usage] = field(default_factory=dict)  # message id -> usage snapshot
    result: dict | None = None
    init: dict | None = None
    rate_limit: dict | None = None
    aux: dict[str, Usage] = field(default_factory=dict)  # other models Claude Code called
    hook_events: dict[str, int] = field(default_factory=dict)
    long_context_calls: int = 0
    unpriced_models: list[str] = field(default_factory=list)

    @property
    def usage_source(self) -> str:
        return "result" if self.result and self.result.get("usage") else "per_call"

    @property
    def usage(self) -> Usage:
        """Usage of the benchmarked model.

        The `result` event's totals are authoritative: per-message usage in the stream is
        a snapshot taken while the response is still streaming, so its output count is
        incomplete (observed: 12 vs 1116 output tokens on Claude Code 2.1.252). Per-call
        sums are only a fallback for sessions that end without a result.
        """
        if self.usage_source == "result":
            return usage_from_api(self.result["usage"])
        total = Usage()
        for u in self.calls.values():
            total = add_usage(total, u)
        return total


def _model_usage(raw: dict) -> Usage:
    """`modelUsage` entries use camelCase and no cache-TTL split (counted as 5-minute)."""
    return Usage(
        input=int(raw.get("inputTokens") or 0),
        cache_write_5m=int(raw.get("cacheCreationInputTokens") or 0),
        cache_read=int(raw.get("cacheReadInputTokens") or 0),
        output=int(raw.get("outputTokens") or 0),
    )


class StreamParser:
    """Incrementally parse stream-json lines; report the cost added by each line.

    While streaming, cost is an estimate from per-message usage snapshots (keyed by
    message id, since Claude Code repeats them once per content block) plus thinking-token
    estimates, so budget caps can act mid-run. The `result` event then reconciles the
    estimate to the session's final totals, including background calls Claude Code makes
    on other models (`modelUsage`).
    """

    def __init__(self, price: Price, aux_prices: dict[str, Price] | None = None):
        self.price = price
        self.aux_prices = aux_prices or {}
        self.state = StreamResult()
        self._cost_by_id: dict[str, float] = {}
        self._charged = 0.0

    def _charge(self, amount: float) -> float:
        amount = max(amount, 0.0)
        self._charged += amount
        return amount

    def cost(self) -> dict[str, float]:
        """API-equivalent cost by token type, benchmarked model plus background models."""
        parts, self.state.long_context_calls = tiered_cost(
            self.state.usage, self.price, list(self.state.calls.values())
        )
        for model, usage in self.state.aux.items():
            price = self.aux_prices.get(model)
            if price is None:
                continue
            for k, v in cost_breakdown(usage, price).items():
                parts[k] += v
        return parts

    def _main_model(self) -> str:
        model = (self.state.init or {}).get("model") or self.price.model
        return model.removeprefix("anthropic.")

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
        elif etype == "system" and "hook" in str(event.get("subtype") or ""):
            name = event.get("hook_event") or event.get("hook_event_name") or event.get("hook_name")
            key = f"{event.get('subtype')}:{name}"
            self.state.hook_events[key] = self.state.hook_events.get(key, 0) + 1
        elif etype == "system" and event.get("subtype") == "thinking_tokens":
            delta = int(event.get("estimated_tokens_delta") or 0)
            return self._charge(delta * self.price.output / 1_000_000)
        elif etype == "rate_limit_event":
            info = event.get("rate_limit_info") or {}
            self.state.rate_limit = info
            status = str(info.get("status") or "")
            if status and not status.startswith("allowed"):
                raise UsageLimitReached(
                    f"rate limit status {status!r} ({info.get('rateLimitType')})",
                    info.get("resetsAt"),
                )
        elif etype == "assistant":
            msg = event.get("message") or {}
            mid, raw = msg.get("id"), msg.get("usage")
            if event.get("error") or event.get("is_api_error_message"):
                text = _assistant_text(msg)
                if looks_like_usage_limit(text):
                    raise UsageLimitReached(text[:300], parse_reset_epoch(text))
                if _is_auth_failure(text, event.get("error")):
                    raise AgentFatalError(text[:300])
                return 0.0
            if mid and raw and msg.get("model") != "<synthetic>":
                usage = usage_from_api(raw)
                self.state.calls[mid] = usage
                new = cost_breakdown(usage, price_for_call(self.price, usage))["total"]
                delta = new - self._cost_by_id.get(mid, 0.0)
                self._cost_by_id[mid] = new
                return self._charge(delta)
        elif etype == "result":
            self.state.result = event
            text = str(event.get("result") or "")
            if event.get("is_error"):
                if event.get("api_error_status") == 429 or looks_like_usage_limit(text):
                    raise UsageLimitReached(text[:300], parse_reset_epoch(text))
                if _is_auth_failure(text):
                    raise AgentFatalError(text[:300])
            main = self._main_model()
            for model, raw in (event.get("modelUsage") or {}).items():
                if model.removeprefix("anthropic.") == main:
                    continue
                self.state.aux[model] = _model_usage(raw)
                canonical = raw.get("canonicalModel")
                if model not in self.aux_prices and canonical in self.aux_prices:
                    self.aux_prices[model] = self.aux_prices[canonical]
                if model not in self.aux_prices:
                    self.state.unpriced_models.append(model)
            # Reconcile the streaming estimate to the final totals.
            return self._charge(self.cost()["total"] - self._charged)
        return 0.0


def _assistant_text(msg: dict) -> str:
    parts = msg.get("content") or []
    return " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
