from inventory import apply_discount, total_price


def test_total_price_sums_line_items():
    items = [
        {"price": 10.0, "quantity": 2},
        {"price": 5.0, "quantity": 3},
    ]
    assert total_price(items) == 35.0


def test_apply_discount_ten_percent():
    # Deliberately wrong expected value to trigger a rewritten assertion diff.
    assert apply_discount(100, 10) == 90.0


def test_total_price_with_priced_catalog(mock_priced_catalog):
    items = [{"price": mock_priced_catalog["widget"], "quantity": 1}]
    assert total_price(items) == 9.99
