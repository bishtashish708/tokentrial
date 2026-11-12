"""Stand-in for the `claude` CLI used by tests. Never calls a model.

Event shapes follow real Claude Code 2.1.252 output (see tests/fixtures/).

Behaviour is chosen by environment variables:
  FAKE_SCENARIO   solve | nothing | usage_limit | expensive | auth_fail | api_error
                  | rate_limited
  FAKE_SOLUTION   directory copied into cwd for the "solve" scenario
  FAKE_COUNTER    file counting invocations; with FAKE_LIMIT_AFTER=N the
                  N+1th and later sessions report a usage limit
  FAKE_ARGV_LOG   append each session's argv to this file
"""

import json
import os
import shutil
import sys
from pathlib import Path


def emit(obj):
    print(json.dumps(obj), flush=True)


def main():
    args = sys.argv[1:]
    if args[:2] == ["auth", "status"]:
        emit({"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "max"})
        return
    if args == ["--version"]:
        print("0.0.0 (fake)")
        return
    assert "--print" in args and "stream-json" in args
    if os.environ.get("FAKE_ARGV_LOG"):
        with open(os.environ["FAKE_ARGV_LOG"], "a") as f:
            f.write(" ".join(args) + "\n")
    sys.stdin.read()

    scenario = os.environ.get("FAKE_SCENARIO", "solve")
    counter = os.environ.get("FAKE_COUNTER")
    if counter:
        p = Path(counter)
        n = int(p.read_text()) if p.exists() else 0
        p.write_text(str(n + 1))
        if n >= int(os.environ.get("FAKE_LIMIT_AFTER", "999999")):
            scenario = "usage_limit"

    emit(
        {
            "type": "system",
            "subtype": "init",
            "model": "claude-haiku-5-5",
            "tools": ["Read"],
            "mcp_servers": [],
            "claude_code_version": "0.0.0",
        }
    )
    emit(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {
                "status": "rejected" if scenario == "rate_limited" else "allowed",
                "resetsAt": 1893456000,
                "rateLimitType": "five_hour",
                "unifiedWindows": {"five_hour": {"utilization": 0.1}},
            },
        }
    )
    if scenario == "rate_limited":
        return

    if scenario == "auth_fail":
        emit(
            {
                "type": "assistant",
                "error": "authentication_failed",
                "is_api_error_message": True,
                "message": {
                    "id": "x",
                    "model": "<synthetic>",
                    "usage": {"input_tokens": 0},
                    "content": [
                        {
                            "type": "text",
                            "text": "Failed to authenticate: OAuth session expired "
                            "and could not be refreshed",
                        }
                    ],
                },
            }
        )
        emit(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "terminal_reason": "api_error",
                "api_error_status": None,
                "result": "Failed to authenticate: OAuth session expired",
            }
        )
        return
    if scenario == "api_error":
        emit(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "terminal_reason": "api_error",
                "api_error_status": 500,
                "result": "API Error: 500 internal",
            }
        )
        return
    if scenario == "usage_limit":
        emit(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "result": "Claude AI usage limit reached|1893456000",
            }
        )
        return

    tokens = 5_000_000 if scenario == "expensive" else 1000
    usage = {
        "input_tokens": 100,
        "cache_creation_input_tokens": 2000,
        "cache_read_input_tokens": tokens,
        "output_tokens": 300,
        "cache_creation": {"ephemeral_5m_input_tokens": 2000, "ephemeral_1h_input_tokens": 0},
    }
    # Streaming snapshots carry an early, incomplete output count, repeated once per
    # content block under the same message id, as real Claude Code does.
    msg = {
        "id": "msg_1",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "usage": {**usage, "output_tokens": 3},
    }
    emit({"type": "assistant", "message": {**msg, "content": [{"type": "text", "text": "a"}]}})
    emit({"type": "assistant", "message": {**msg, "content": [{"type": "text", "text": "b"}]}})
    emit({"type": "system", "subtype": "thinking_tokens", "estimated_tokens_delta": 40})
    if scenario == "solve":
        shutil.copytree(os.environ["FAKE_SOLUTION"], os.getcwd(), dirs_exist_ok=True)
    emit(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "num_turns": 2,
            "total_cost_usd": 0.01,
            "result": "done",
            "usage": usage,
            "modelUsage": {
                "claude-haiku-5-5": {"inputTokens": 100},
                "claude-haiku-4-5-20251001": {
                    "inputTokens": 900,
                    "outputTokens": 10,
                    "canonicalModel": "claude-haiku-4-5",
                },
            },
        }
    )


if __name__ == "__main__":
    main()
