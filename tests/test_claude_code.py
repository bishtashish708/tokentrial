import json
from pathlib import Path

import pytest

from tokentrial.claude_code import (
    StreamParser,
    UsageLimitReached,
    build_command,
    child_env,
    looks_like_usage_limit,
    parse_reset_epoch,
)
from tokentrial.pricing import Price, cost_breakdown

PRICE = Price(
    "anthropic", "m", input=1, cache_write_5m=1.25, cache_write_1h=2, cache_read=0.1, output=5
)


def _assistant(mid, **usage):
    return json.dumps({"type": "assistant", "message": {"id": mid, "usage": usage}})


def test_duplicate_message_ids_are_not_double_counted():
    p = StreamParser(PRICE)
    first = p.feed(_assistant("m1", input_tokens=1_000_000, output_tokens=0))
    second = p.feed(_assistant("m1", input_tokens=1_000_000, output_tokens=0))
    assert first == pytest.approx(1.0)
    assert second == 0
    assert p.state.usage.input == 1_000_000


def test_usage_split_by_type_and_ttl():
    p = StreamParser(PRICE)
    p.feed(
        _assistant(
            "m1",
            input_tokens=10,
            cache_read_input_tokens=20,
            output_tokens=5,
            cache_creation_input_tokens=7,
            cache_creation={"ephemeral_5m_input_tokens": 3, "ephemeral_1h_input_tokens": 4},
        )
    )
    p.feed(_assistant("m2", input_tokens=1, cache_creation_input_tokens=6))
    u = p.state.usage
    assert (u.input, u.cache_read, u.output) == (11, 20, 5)
    assert (u.cache_write_5m, u.cache_write_1h) == (9, 4)


def test_result_totals_override_streaming_snapshots():
    p = StreamParser(PRICE)
    p.feed(_assistant("m1", input_tokens=10, output_tokens=2))
    p.feed(
        json.dumps(
            {
                "type": "result",
                "is_error": False,
                "usage": {"input_tokens": 10, "output_tokens": 500},
            }
        )
    )
    assert p.state.usage.output == 500


def test_result_totals_used_when_no_per_call_usage():
    p = StreamParser(PRICE)
    p.feed(
        json.dumps(
            {"type": "result", "is_error": False, "usage": {"input_tokens": 5, "output_tokens": 2}}
        )
    )
    assert p.state.usage.input == 5


def test_usage_limit_result_raises_with_reset_time():
    p = StreamParser(PRICE)
    with pytest.raises(UsageLimitReached) as e:
        p.feed(
            json.dumps(
                {
                    "type": "result",
                    "is_error": True,
                    "result": "Claude AI usage limit reached|1893456000",
                }
            )
        )
    assert e.value.reset_epoch == 1893456000


def test_ordinary_error_result_does_not_raise():
    p = StreamParser(PRICE)
    p.feed(json.dumps({"type": "result", "is_error": True, "result": "max turns"}))
    assert p.state.result["is_error"]


@pytest.mark.parametrize(
    "text",
    [
        "Claude AI usage limit reached|1700000000",
        "You've hit your limit · resets 3pm",
        "API Error: 429 rate_limit_error",
    ],
)
def test_limit_detection(text):
    assert looks_like_usage_limit(text)


def test_reset_epoch_absent():
    assert parse_reset_epoch("hit your limit") is None


def test_command_isolates_user_config_and_reads_prompt_from_stdin():
    cmd = build_command(["claude"], "claude-haiku-5-5")
    for flag in ("--print", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"


def test_subscription_env_drops_api_credentials(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert "ANTHROPIC_API_KEY" not in child_env("subscription")
    assert child_env("api")["ANTHROPIC_API_KEY"] == "x"


def test_auth_failure_is_fatal():
    from tokentrial.claude_code import AgentFatalError

    p = StreamParser(PRICE)
    event = {
        "type": "assistant",
        "error": "authentication_failed",
        "is_api_error_message": True,
        "message": {
            "id": "x",
            "model": "<synthetic>",
            "content": [{"type": "text", "text": "Failed to authenticate"}],
        },
    }
    with pytest.raises(AgentFatalError):
        p.feed(json.dumps(event))


def test_synthetic_messages_are_not_counted_as_api_calls():
    p = StreamParser(PRICE)
    p.feed(
        json.dumps(
            {
                "type": "assistant",
                "message": {"id": "s", "model": "<synthetic>", "usage": {"input_tokens": 0}},
            }
        )
    )
    assert p.state.calls == {}


def test_http_429_result_is_a_usage_limit():
    p = StreamParser(PRICE)
    with pytest.raises(UsageLimitReached):
        p.feed(
            json.dumps(
                {"type": "result", "is_error": True, "api_error_status": 429, "result": "API Error"}
            )
        )


def test_host_claude_session_vars_are_not_inherited(monkeypatch):
    for var in (
        "CLAUDECODE",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH",
        "CLAUDE_CODE_SIMPLE",
    ):
        monkeypatch.setenv(var, "1")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/cfg")
    env = child_env("subscription")
    assert not [k for k in env if k.startswith("ANTHROPIC") or k == "CLAUDECODE"]
    assert "CLAUDE_CODE_SIMPLE" not in env
    assert env["CLAUDE_CONFIG_DIR"] == "/tmp/cfg"
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"


def test_available_tools_are_restricted_not_just_permitted():
    cmd = build_command(["claude"], "m")
    assert cmd[cmd.index("--tools") + 1] == cmd[cmd.index("--allowedTools") + 1]


# --- Real Claude Code 2.1.252 output (smoke run, 2026-11-12) -------------------

FIXTURE = Path(__file__).parent / "fixtures" / "claude-code-2.1.252-haiku-5-5.jsonl"


def _replay(price, aux_prices):
    p = StreamParser(price, aux_prices)
    charged = sum(p.feed(line) for line in FIXTURE.read_text().splitlines())
    return p, charged


def test_real_output_uses_result_totals_not_streaming_snapshots():
    from tokentrial.pricing import load_prices

    prices = load_prices()
    p, _ = _replay(prices[("anthropic", "claude-haiku-5-5")], {})
    u = p.state.usage
    assert p.state.usage_source == "result"
    assert (u.input, u.cache_write_1h, u.cache_read, u.output) == (8, 17039, 43549, 1116)
    # The streaming snapshots alone undercount output (the bug this guards against).
    snapshot_output = sum(c.output for c in p.state.calls.values())
    assert snapshot_output < 50


def test_real_output_counts_background_model_and_reconciles_budget():
    from tokentrial.pricing import load_prices

    prices = load_prices()
    haiku55 = prices[("anthropic", "claude-haiku-5-5")]
    haiku45 = prices[("anthropic", "claude-haiku-4-5")]
    p, charged = _replay(haiku55, {"claude-haiku-4-5": haiku45})
    assert set(p.state.aux) == {"claude-haiku-4-5-20251001"}
    assert p.state.aux["claude-haiku-4-5-20251001"].input == 938
    assert p.state.unpriced_models == []
    total = p.cost()["total"]
    main = cost_breakdown(p.state.usage, haiku55)["total"]
    assert total > main
    assert charged == pytest.approx(total)  # live charges end equal to the final cost


def test_real_output_rate_limit_info_recorded():
    from tokentrial.pricing import load_prices

    p, _ = _replay(load_prices()[("anthropic", "claude-haiku-5-5")], {})
    assert p.state.rate_limit["status"] == "allowed"


def test_rejected_rate_limit_event_pauses():
    p = StreamParser(PRICE)
    event = {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "rejected",
            "resetsAt": 1794465600,
            "rateLimitType": "five_hour",
        },
    }
    with pytest.raises(UsageLimitReached) as e:
        p.feed(json.dumps(event))
    assert e.value.reset_epoch == 1794465600


def test_unpriced_background_model_is_reported():
    p = StreamParser(PRICE)
    p.feed(
        json.dumps(
            {
                "type": "result",
                "is_error": False,
                "usage": {"input_tokens": 1},
                "modelUsage": {"m": {"inputTokens": 1}, "mystery-model": {"inputTokens": 5}},
            }
        )
    )
    assert p.state.unpriced_models == ["mystery-model"]


def test_hook_events_are_counted():
    p = StreamParser(PRICE)
    for _ in range(2):
        p.feed(
            json.dumps(
                {
                    "type": "system",
                    "subtype": "hook_response",
                    "hook_event": "PreToolUse",
                    "hook_name": "PreToolUse:Bash",
                }
            )
        )
    assert p.state.hook_events == {"hook_response:PreToolUse": 2}


def test_command_logs_hook_events():
    assert "--include-hook-events" in build_command(["claude"], "m")
