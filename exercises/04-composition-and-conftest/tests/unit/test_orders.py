import pytest

# `make_order` only lives in this directory's conftest.py, so it is only
# visible to tests under tests/unit/ — that's why all 4 factory tests below
# live here, and tests/integration/ can't use it (that's conftest.py
# discovery working as designed, not an oversight).


def test_make_order_defaults_to_pending_status(make_order):
    order = make_order(["widget"])
    assert order.status == "pending"


def test_make_order_accepts_custom_items(make_order):
    order = make_order(["widget", "gadget", "gizmo"])
    assert order.items == ["widget", "gadget", "gizmo"]


def test_cancel_succeeds_while_status_is_pending(make_order):
    order = make_order(["widget"])
    order.cancel()
    assert order.status == "cancelled"


def test_cancel_fails_once_order_already_shipped(make_order):
    order = make_order(["widget"], status="shipped")
    with pytest.raises(ValueError):
        order.cancel()


def test_app_config_has_no_live_mode_attribute_in_unit_tests(app_config):
    # Proves tests/integration/conftest.py's override doesn't leak sideways
    # into tests/unit/ — this directory only ever sees the root app_config.
    assert not hasattr(app_config, "live_mode")
