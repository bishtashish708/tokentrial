import json
import unittest

from ingestd.worker.batcher import Batcher


class BatcherTest(unittest.TestCase):
    def test_splits_on_size(self):
        b = Batcher(max_bytes=30, max_messages=100)
        out = [b.add({"n": i}) for i in range(6)]
        full = [x for x in out if x is not None]
        self.assertTrue(full)
        for batch in full:
            self.assertLessEqual(len(batch), 30)
            json.loads(batch)

    def test_splits_on_count(self):
        b = Batcher(max_bytes=10_000, max_messages=2)
        self.assertIsNone(b.add(1))
        self.assertIsNone(b.add(2))
        self.assertEqual(b.add(3), b"[1,2]")
        self.assertEqual(b.flush(), b"[3]")


if __name__ == "__main__":
    unittest.main()
