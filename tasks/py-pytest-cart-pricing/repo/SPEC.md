# cartcalc pricing specification

All money is `decimal.Decimal`. "Round" always means: round to whole cents,
halves away from zero (ROUND_HALF_UP). Never use binary floats for money.

1. **Line subtotal.** `unit_price * qty`, with quantity breaks on the unit price:
   qty of 10 or more: 5% off; qty of 50 or more: 10% off (not cumulative).
   Round the line subtotal.
2. **Order subtotal.** Sum of line subtotals.
3. **Discount codes**, applied to the order subtotal:
   - All percentage codes apply first, compounding, in the order given
     (two 10% codes take 19% off in total). Round after each one.
   - Then fixed-amount codes are subtracted, in the order given.
   - The result never goes below 0.00.
4. **Tax.** Each region has a rate (see `cartcalc/tax.py`). Lines whose category
   is exempt (`food`, `books`) are not taxed; category matching ignores case and
   surrounding whitespace. The taxable base is the discounted subtotal multiplied
   by (sum of taxable line subtotals / order subtotal). Tax = round(base * rate).
   An empty order or a zero order subtotal has zero tax.
5. **Total** = discounted subtotal + tax.

Unknown discount codes and unknown regions raise `ValueError`.
