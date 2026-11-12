import unittest

from durations import format_duration, parse_duration


class Parse(unittest.TestCase):
    def test_bare_seconds(self):
        self.assertEqual(parse_duration("90"), 90)

    def test_hours_minutes(self):
        self.assertEqual(parse_duration("1h30m"), 5400)

    def test_all_units(self):
        self.assertEqual(parse_duration("1d2h3m4s"), 93784)

    def test_unknown_unit(self):
        with self.assertRaises(ValueError):
            parse_duration("5w")


class Format(unittest.TestCase):
    def test_hours_minutes(self):
        self.assertEqual(format_duration(5400), "1h30m")

    def test_zero(self):
        self.assertEqual(format_duration(0), "0s")


if __name__ == "__main__":
    unittest.main()
