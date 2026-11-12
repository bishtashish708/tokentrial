import unittest

from durations import format_duration, parse_duration


class Parse(unittest.TestCase):
    def test_valid(self):
        cases = {
            "90": 90, "0": 0, "0s": 0, "1h30m": 5400, "1d2h3m4s": 93784, "45s": 45,
            "2m15s": 135, "1d": 86400, "1H30M": 5400, " 1h 30m ": 5400, "1d 1s": 86401,
            "100m": 6000,
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), want)

    def test_invalid(self):
        for text in ["", "   ", "5w", "-5", "+5m", "1.5h", "h", "1h30", "30m1h", "1h1h",
                     "1 h", "abc", "1h-30m", "s1"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_duration(text)


class Format(unittest.TestCase):
    def test_values(self):
        cases = {0: "0s", 1: "1s", 59: "59s", 60: "1m", 90: "1m30s", 3600: "1h",
                 5400: "1h30m", 86400: "1d", 90061: "1d1h1m1s", 172800: "2d"}
        for n, want in cases.items():
            with self.subTest(n=n):
                self.assertEqual(format_duration(n), want)

    def test_invalid(self):
        for value in [-1, 1.5, True, "60"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                format_duration(value)

    def test_round_trip(self):
        for n in list(range(0, 4000, 7)) + [86399, 86400, 86401, 10**6]:
            self.assertEqual(parse_duration(format_duration(n)), n)
        for text in ["1h30m", "1d2h3m4s", "45s", "1d"]:
            self.assertEqual(format_duration(parse_duration(text)), text)


if __name__ == "__main__":
    unittest.main()
