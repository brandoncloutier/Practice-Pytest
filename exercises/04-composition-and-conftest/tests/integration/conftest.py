"""tests/integration/conftest.py — fixtures here are visible only to tests
in tests/integration/ (and any subdirectories under it), not to
tests/unit/.

Pattern-match the style of the root conftest.py two directories up.
"""

from types import SimpleNamespace

import pytest


# TODO: write a fixture called `app_config` that OVERRIDES the root
# conftest.py's `app_config` fixture, but only for tests under
# tests/integration/ (Lesson 04's "same-name override" pattern). It should:
#
#   - Have the exact same name, `app_config`, as the root fixture.
#   - Take a parameter also named `app_config` — pytest resolves this to
#     mean "give me the next-outer-scope version of this fixture" (i.e. the
#     session-scoped one from the root conftest.py), not infinite recursion.
#   - Build and return a NEW SimpleNamespace that copies the outer
#     app_config's existing attributes and adds `live_mode=True`, e.g.
#     `SimpleNamespace(**vars(app_config), live_mode=True)`.
#
#     Careful: the outer app_config is session-scoped, meaning it's ONE
#     object shared by the entire test run, across both tests/unit/ and
#     tests/integration/. If you mutate that object directly (e.g.
#     `app_config.live_mode = True; return app_config`) instead of copying
#     it, you'll permanently set `live_mode` on the single shared instance —
#     and depending on which directory pytest collects first, that can leak
#     into tests/unit/ too, silently breaking the "no leak" test over there.
#     This is the same "mutable object at wide scope" pitfall from Lesson 03,
#     showing up again here in the context of overriding.
#
# @pytest.fixture
# def app_config(app_config):
#     ...
