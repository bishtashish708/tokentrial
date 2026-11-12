"""Hidden check: seeded generated cases (see scripts/make_dedupe_task.py)."""

import copy
import json
import unittest
from pathlib import Path

from contactdedupe import dedupe

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


class TestReferenceCases(unittest.TestCase):
    def test_cases(self):
        for k, case in enumerate(CASES):
            with self.subTest(case=k, n=len(case["input"])):
                records = copy.deepcopy(case["input"])
                self.assertEqual(dedupe(records), case["expected"])
                self.assertEqual(records, case["input"])


if __name__ == "__main__":
    unittest.main()
