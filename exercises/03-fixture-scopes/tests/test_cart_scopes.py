# Lesson 03 exercise — session-scoped vs. function-scoped fixtures.
#
# Run `pytest -v` on this file. One test in the "BROKEN" section below will
# fail. Before scrolling down to the spoiler block, try to answer for
# yourself:
#
#   - Which fixture does the failing test use, and what scope is it?
#   - What does that fixture return, and is that return value mutable?
#   - Which other tests run before the failing one, and what do they do to
#     that same return value?
#   - Why does the "FIXED" section below not have the same problem?
#
# Write your own one- or two-sentence explanation of the bug before reading
# past the marker.
#
# """SPOILER BELOW - try to explain the bug in a comment first before reading this"""
#
# The bug: `shared_cart` is `scope="session"`, so pytest constructs the list
# ONCE for the entire test session and hands every test the *same* list
# object, not a fresh one per test. `test_first_customer_adds_apple` and
# `test_second_customer_adds_banana` each append to it and pass, but they're
# secretly accumulating state in one shared list — `test_second_customer...`
# only passes because it (incorrectly) expects to see the first customer's
# "apple" still sitting there. By the time
# `test_new_customer_cart_starts_fresh` runs, the "fresh" cart it asked for
# already contains two other customers' leftover items, so its assertion
# that the cart contains only its own item fails. The fix is `fresh_cart`
# below: `scope="function"` (the default) constructs a brand-new empty list
# for every single test, so nothing can leak between tests no matter what
# order they run in.

import pytest


# ---------------------------------------------------------------------------
# BROKEN: session-scoped fixture returning a mutable list
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def shared_cart():
    return []


def test_first_customer_adds_apple(shared_cart):
    shared_cart.append("apple")
    assert shared_cart == ["apple"]


def test_second_customer_adds_banana(shared_cart):
    shared_cart.append("banana")
    assert shared_cart == ["apple", "banana"]


def test_new_customer_cart_starts_fresh(shared_cart):
    shared_cart.append("milk")
    # A new customer's cart should only contain what they themselves added.
    assert shared_cart == ["milk"]


# ---------------------------------------------------------------------------
# FIXED: function-scoped fixture returning a fresh list per test
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_cart():
    return []


def test_first_customer_adds_apple_isolated(fresh_cart):
    fresh_cart.append("apple")
    assert fresh_cart == ["apple"]


def test_second_customer_adds_banana_isolated(fresh_cart):
    fresh_cart.append("banana")
    assert fresh_cart == ["banana"]


def test_new_customer_cart_starts_fresh_isolated(fresh_cart):
    fresh_cart.append("milk")
    assert fresh_cart == ["milk"]
