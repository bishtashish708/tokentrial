"""Queue message envelopes: routing headers plus an HMAC over the payload."""

import hashlib
import hmac
import json
import time
import uuid

ENVELOPE_VERSION = 3


def wrap(payload: bytes, key: bytes = b"ingestd") -> bytes:
    header = {
        "v": ENVELOPE_VERSION,
        "id": uuid.uuid4().hex,
        "ts": int(time.time() * 1000),
        "len": len(payload),
        "sig": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }
    return json.dumps(header).encode() + b"\n" + payload


def unwrap(message: bytes, key: bytes = b"ingestd") -> bytes:
    head, _, payload = message.partition(b"\n")
    header = json.loads(head)
    if header.get("v") != ENVELOPE_VERSION:
        raise ValueError(f"unsupported envelope version {header.get('v')}")
    if len(payload) != header["len"]:
        raise ValueError("truncated message")
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, header["sig"]):
        raise ValueError("bad signature")
    return payload
