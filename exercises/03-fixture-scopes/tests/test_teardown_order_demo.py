# Lesson 03 exercise — observe actual fixture teardown order.
#
# Run: pytest -s -v test_teardown_order_demo.py
#
# `-s` disables output capturing so the print()s below are visible; `-v`
# prints each test name as it runs so you can line the prints up against
# which test triggered them.
#
# Read the printed order and confirm for yourself:
#   - `session_fixture` sets up once, before anything else, and tears down
#     once, after everything else — it outlives every test in this file.
#   - `module_fixture` sets up once (after `session_fixture`) and tears down
#     once (before `session_fixture`'s teardown) — it outlives every test in
#     this module, but not the whole session.
#   - `function_fixture` sets up and tears down once per test, always fully
#     nested inside both wider-scoped fixtures' lifetimes.
#   - Teardown order is the reverse of setup order (LIFO) at every level.

import pytest


@pytest.fixture(scope="session")
def session_fixture():
    print("\nSETUP    session_fixture")
    yield
    print("TEARDOWN session_fixture")


@pytest.fixture(scope="module")
def module_fixture(session_fixture):
    print("SETUP    module_fixture")
    yield
    print("TEARDOWN module_fixture")


@pytest.fixture
def function_fixture(module_fixture):
    print("SETUP    function_fixture")
    yield
    print("TEARDOWN function_fixture")


def test_one(function_fixture):
    print("RUN      test_one")


def test_two(function_fixture):
    print("RUN      test_two")


def test_three(function_fixture):
    print("RUN      test_three")
