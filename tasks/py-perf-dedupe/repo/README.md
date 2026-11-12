# contactdedupe

Merges duplicate contacts exported from our CRM before they are loaded into the mailing
platform. The exact semantics are in [SPEC.md](SPEC.md).

```
python3 -m contactdedupe contacts.jsonl merged.jsonl
```

Input and output are JSON Lines, one contact per line.

## Batch size

The nightly export job runs `dedupe` on batches of **up to 200,000 contacts**. Each batch
must be deduplicated in a few seconds on the export worker (a small, slow VM). The current
implementation was written for the old 1,000-contact batches and does not keep up.

## Development

Standard library only, Python 3.11+.

```
python3 -m unittest discover -s tests
```
