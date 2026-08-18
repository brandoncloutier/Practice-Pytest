from inventory import apply_discount, total_price


def check_total_price_empty_cart():
    assert total_price([]) == 0


def check_apply_discount_zero_percent():
    assert apply_discount(50, 0) == 50
