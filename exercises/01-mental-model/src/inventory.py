"""Small pure functions for inventory pricing math."""


def total_price(items):
    """items: iterable of dicts with 'price' and 'quantity' keys."""
    return sum(item["price"] * item["quantity"] for item in items)


def apply_discount(price, percent):
    """Apply a percentage discount to a price.

    Note: percent is not validated — callers are expected to pass a
    sane value in [0, 100].
    """
    return price - (price * percent / 100)
