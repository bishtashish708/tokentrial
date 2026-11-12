import json

import pytest

from tokentrial.claude_code import (
    StreamParser,
    UsageLimitReached,
    build_command,
    child_env,
    looks_like_usage_limit,
    parse_reset_epoch,
)
from tokentrial.pricing import Price

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
