"""Write each batch to its own file under a date-partitioned directory."""

import gzip
import os
import threading
import time
import uuid


class FileSink:
    def __init__(self, root, compress=False):
        self.root = root
        self.compress = compress
        self._lock = threading.Lock()

    def write(self, batch: bytes):
        day = time.strftime("%Y/%m/%d", time.gmtime())
        directory = os.path.join(self.root, day)
        os.makedirs(directory, exist_ok=True)
        name = uuid.uuid4().hex + (".json.gz" if self.compress else ".json")
        tmp = os.path.join(directory, "." + name)
        opener = gzip.open if self.compress else open
        with opener(tmp, "wb") as fh:
            fh.write(batch)
        os.replace(tmp, os.path.join(directory, name))

    def close(self):
        pass
