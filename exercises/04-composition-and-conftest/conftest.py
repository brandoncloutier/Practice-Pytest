"""Root conftest.py — fixtures here are visible to every test in this
project, in tests/unit/ and tests/integration/ alike.

This file is pre-written as a working example. Pattern-match its style when
you write tests/unit/conftest.py and tests/integration/conftest.py.
"""

from types import SimpleNamespace

import pytest


@pytest.fixture(scope="session")
def app_config():
    """Application configuration shared by the whole test session.

    session-scoped: constructed once for the entire pytest run, then reused
    by every test that requests it. It's a plain, mutable SimpleNamespace on
    purpose — that's what lets tests/integration/conftest.py demonstrate
    fixture *overriding*: it will request this exact fixture (by depending
    on a same-named `app_config` parameter) and add an attribute to it,
    without touching this definition at all.
    """
    return SimpleNamespace(env="test")
