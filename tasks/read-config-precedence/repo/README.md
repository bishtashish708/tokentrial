# ingestd

`ingestd` accepts batches of JSON events over HTTP, wraps them in queue envelopes and
hands them to a pool of workers that write them to a sink (local files for now).

```
python3 -m ingestd serve                       # uses config/ingestd.conf
python3 -m ingestd serve --profile prod --workers 8
python3 -m ingestd check-config --config path/to/other.conf
```

See docs/configuration.md for how settings are resolved.

Tests: `python3 -m unittest discover -s tests`
