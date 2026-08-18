"""tests/unit/conftest.py — fixtures here are visible only to tests in
tests/unit/ (and any subdirectories under it), not to tests/integration/.

Pattern-match the style of the root conftest.py one directory up.
"""

import pytest

# from order import Order   # already written for you in src/order.py


# TODO: write a fixture called `make_order` using the factory-as-fixture
# pattern (Lesson 04). It should:
#
#   - Return a FUNCTION (not an Order directly) — call it e.g. `_make_order`
#     — so each test can call `make_order(...)` as many times as it wants,
#     with different arguments, to get differently-configured Orders.
#   - The inner function should accept `items: list[str]` and an optional
#     `status` keyword defaulting to `"pending"`, construct an
#     `Order(items, status=status)` (imported from the `order` module —
#     already written for you in src/order.py), and return it.
#   - `Order` has no external resources (no file handles, no network, no
#     database rows) to clean up, so a plain `return` fixture (not `yield`)
#     is enough here — there's nothing to track or tear down, unlike the
#     `make_user` example in the lesson which had to append every created
#     user to a list for cleanup.
#
# @pytest.fixture
# def make_order():
#     def _make_order(items, status="pending"):
#         ...
#     return _make_order
