from ingestd.sinks.file_sink import FileSink


def make_sink(cfg, service_cfg):
    if cfg["kind"] == "file":
        return FileSink(cfg["path"], compress=cfg["compress"])
    raise RuntimeError(f"unknown sink kind {cfg['kind']!r}")
