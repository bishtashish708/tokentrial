"""Product catalog."""

PRICES_CENTS = {
    "sku-tee": 1999, "sku-mug": 1250, "sku-cap": 2200, "sku-sock": 899, "sku-bag": 4500,
    "sku-pen": 299, "sku-note": 650, "sku-hood": 5400, "sku-pin": 450, "sku-band": 1100,
}


def price_of(sku: str) -> int:
    try:
        return PRICES_CENTS[sku]
    except KeyError:
        raise KeyError(f"unknown sku {sku}") from None
