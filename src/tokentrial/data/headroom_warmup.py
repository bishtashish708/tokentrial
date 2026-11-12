"""Run headroom's compressor once so its local model is downloaded at install time."""

from headroom import compress

log = "\n".join(f"line {i}: INFO request ok id={i * 7919 % 10007}" for i in range(600))
msgs = [
    {"role": "user", "content": "Summarise the log."},
    {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "cat log"}}
        ],
    },
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": log}]},
]
result = compress(msgs, model="claude-haiku-5-5")
print("tokens_saved", result.tokens_saved)
