import unittest
from decimal import Decimal

from ledger import balance, format_amount, parse_amount


class ParseAmount(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_amount("12"), Decimal("12"))

    def test_decimal(self):
        self.assertEqual(parse_amount("12.50"), Decimal("12.50"))

    def test_dollar_sign(self):
        self.assertEqual(parse_amount("$7.25"), Decimal("7.25"))

    def test_thousands_separator(self):
        self.assertEqual(parse_amount("$1,234.50"), Decimal("1234.50"))

    def test_minus_sign(self):
        self.assertEqual(parse_amount("-3.00"), Decimal("-3.00"))

    def test_whitespace(self):
        self.assertEqual(parse_amount("  $5 "), Decimal("5"))

    def test_parentheses_are_negative(self):
        self.assertEqual(parse_amount("(12.00)"), Decimal("-12.00"))

    def test_parentheses_with_dollar(self):
        self.assertEqual(parse_amount("($1,000.00)"), Decimal("-1000.00"))

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_amount("twelve")


class Balance(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(balance([]), Decimal("0"))

    def test_positive_only(self):
        self.assertEqual(balance(["$1.00", "2.50"]), Decimal("3.50"))

    def test_mixed_with_accounting_negative(self):
        self.assertEqual(balance(["$100.00", "(40.00)", "-10"]), Decimal("50.00"))


class FormatAmount(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(format_amount(Decimal("1234.5")), "$1,234.50")

    def test_negative(self):
        self.assertEqual(format_amount(Decimal("-12")), "($12.00)")

    def test_round_trip_negative(self):
        self.assertEqual(format_amount(parse_amount("($9.99)")), "($9.99)")


if __name__ == "__main__":
    unittest.main()
