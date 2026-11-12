import unittest

from helpers import DATA, run

SHOP = DATA / "shop.lock"


class TestTextOutput(unittest.TestCase):
    def assertOutput(self, args, code, stdout, stderr=""):
        self.assertEqual(run(*args), (code, stdout, stderr))

    def test_summary(self):
        self.assertOutput(["-f", SHOP, "summary"], 0,
                          "project: shop-api (4 direct dependencies)\n"
                          "packages: 11 (10 distinct names)\n"
                          "sources: git 1, path 1, registry 9\n")

    def test_licenses(self):
        self.assertOutput(["-f", SHOP, "licenses"], 0, """\
11 packages
  permissive     8
  copyleft       1
  unknown        2

Apache-2.0    requests 2.31.0
BSD-3-Clause  idna 3.10, idna 3.9, click 8.1.7
GPL-3.0       gplthing 1.0
MIT           urllib3 2.0.7, charset-normalizer 3.3.2, pyyaml 5.4.1
Proprietary   stripe-sdk 7.0.0
PSF-2.0       typing-ext 4.8.0
(none)        nolicense 0.0.1
""")

    def test_licenses_only_direct_fail_on(self):
        self.assertOutput(["-f", SHOP, "licenses", "--only-direct", "--fail-on", "unknown"], 1, """\
4 packages (direct dependencies only)
  permissive     3
  copyleft       0
  unknown        1

Apache-2.0    requests 2.31.0
BSD-3-Clause  click 8.1.7
MIT           pyyaml 5.4.1
Proprietary   stripe-sdk 7.0.0

FAILED: 1 unknown package found
""")

    def test_check(self):
        self.assertOutput(["-f", SHOP, "check"], 1, """\
lockscan check: 3 errors, 3 warnings
error   unsatisfied  shop-api -> pyyaml >= 6 (locked: 5.4.1)
error   missing      requests 2.31.0 -> certifi>=2017.4.17 (not locked)
error   missing      click 8.1.7 -> colorama (not locked)
warning duplicate    idna (3.9, 3.10)
warning orphan       gplthing 1.0
warning orphan       nolicense 0.0.1
""")

    def test_check_clean_strict(self):
        self.assertOutput(["-f", DATA / "clean.lock", "check", "--strict"], 0,
                          "lockscan check: no problems found\n")

    def test_why(self):
        self.assertOutput(["-f", SHOP, "why", "requests"], 0, """\
requests is required by:
  shop-api (project)  (requests>=2.28)
  stripe-sdk 7.0.0    (requests>=2.20)
""")

    def test_tree_depth(self):
        self.assertOutput(["-f", SHOP, "tree", "--depth", "1"], 0, """\
shop-api
|-- requests 2.31.0
|-- click 8.1.7
|-- pyyaml 5.4.1
`-- stripe-sdk 7.0.0
""")

    def test_errors(self):
        self.assertOutput(["-f", "does-not-exist.lock", "check"], 2, "",
                          "lockscan: error: cannot read does-not-exist.lock: "
                          "No such file or directory\n")
        bad = DATA / "badversion.lock"
        self.assertOutput(["-f", bad, "licenses"], 2, "",
                          f"lockscan: error: {bad}: package #1: invalid version '1.0-beta'\n")


if __name__ == "__main__":
    unittest.main()
