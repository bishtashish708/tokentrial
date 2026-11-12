import json
import unittest

from helpers import DATA, run

SHOP = DATA / "shop.lock"


class TestJsonOutput(unittest.TestCase):
    def run_json(self, *args):
        code, out, err = run(*args)
        self.assertEqual(err, "")
        return code, json.loads(out)

    def test_licenses_clean(self):
        code, doc = self.run_json("-f", DATA / "clean.lock", "licenses", "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(doc, {
            "packages": [
                {"name": "alpha", "version": "1.0.0", "license": "MIT",
                 "category": "permissive", "direct": True},
                {"name": "beta", "version": "1.2", "license": "ISC",
                 "category": "permissive", "direct": False},
            ],
            "counts": {"permissive": 2, "copyleft": 0, "unknown": 0},
            "failed": False,
        })

    def test_check_shop(self):
        code, doc = self.run_json("-f", SHOP, "check", "--format", "json")
        self.assertEqual(code, 1)
        self.assertEqual(doc["ok"], False)
        self.assertEqual(doc["counts"], {"errors": 3, "warnings": 3})
        self.assertEqual(doc["issues"][0], {
            "kind": "duplicate", "severity": "warning", "package": "idna", "version": None,
            "dependency": None, "requirement": None, "found": ["3.9", "3.10"],
        })
        self.assertEqual([i["kind"] for i in doc["issues"]],
                         ["duplicate", "missing", "missing", "orphan", "orphan", "unsatisfied"])

    def test_missing_file(self):
        code, doc = self.run_json("-f", "does-not-exist.lock", "check", "--format", "json")
        self.assertEqual(code, 3)
        self.assertEqual(doc["error"]["code"], "read_error")

    def test_text_is_default(self):
        self.assertEqual(run("-f", SHOP, "check", "--format", "text"), run("-f", SHOP, "check"))


if __name__ == "__main__":
    unittest.main()
