import unittest

from ingestd.config.errors import ConfigError
from ingestd.config.units import format_size, parse_bool, parse_size


class SizeTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(parse_size("512"), 512)
        self.assertEqual(parse_size("64k"), 64000)
        self.assertEqual(parse_size("64KiB"), 65536)
        self.assertEqual(parse_size("2MB"), 2000000)
        self.assertEqual(parse_size(" 2 MiB "), 2097152)
        self.assertEqual(parse_size(7), 7)

    def test_invalid(self):
        for bad in ("", "1.5MiB", "12 parsecs", "-1", True):
            with self.assertRaises(ConfigError):
                parse_size(bad)

    def test_format(self):
        self.assertEqual(format_size(8388608), "8MiB")
        self.assertEqual(format_size(1000), "1000")

    def test_bool(self):
        self.assertTrue(parse_bool("Yes"))
        self.assertFalse(parse_bool("off"))


if __name__ == "__main__":
    unittest.main()
