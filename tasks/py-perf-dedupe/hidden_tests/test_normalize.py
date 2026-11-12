import unittest

from contactdedupe import normalize_email, normalize_phone


class TestEmail(unittest.TestCase):
    def test_cases(self):
        cases = [
            (None, None),
            ("  Alice@Example.COM ", "alice@example.com"),
            ("a.l.i.c.e+news@gmail.com", "alice@gmail.com"),
            ("A.Lice@GoogleMail.com", "alice@gmail.com"),
            ("bob.smith+work@outlook.com", "bob.smith@outlook.com"),
            ("bob.smith+work@example.com", "bob.smith+work@example.com"),
            ("+promo@gmail.com", None),
            ("...@gmail.com", None),
            ("no-at-sign", None),
            ("two@@ats.com", None),
            ("@example.com", None),
            ("user@", None),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_email(raw), expected)


class TestPhone(unittest.TestCase):
    def test_cases(self):
        cases = [
            (None, None),
            ("(555) 123-4567", "5551234567"),
            ("+1 555 123 4567", "5551234567"),
            ("1-555-123-4567", "5551234567"),
            ("2-555-123-4567", None),
            ("555-1234", None),
            ("", None),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), expected)


if __name__ == "__main__":
    unittest.main()
