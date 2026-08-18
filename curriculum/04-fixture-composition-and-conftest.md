# Lesson 04 — Fixture Composition, Factories & conftest.py

Phase 2: Fixtures & Parametrization Mastery

## Learning Objectives

- Build fixtures that depend on other fixtures to model layered setup.
- Write and use the **factory-as-fixture** pattern for tests that need
  several differently-configured instances of something.
- Explain how `conftest.py` discovery works across a directory tree, and how
  fixture name resolution picks a "closest" definition when names collide.
- Override a fixture at a narrower scope (e.g. per-file) without touching the
  shared, broader definition.

## Why This Matters in Production

Real production suites have hundreds or thousands of tests sharing setup
logic — a database connection, an authenticated API client, sample domain
objects — but not every test wants the exact same shape of that setup. The
tools in this lesson (composition, factories, `conftest.py` layering) are how
teams avoid a `conftest.py` with fifty near-identical fixtures called
`user_admin`, `user_admin_no_email`, `user_admin_inactive`, and instead have a
handful of composable building blocks.

## Concept: Fixtures Depending on Fixtures

You saw a preview of this in Lesson 02. It's worth being explicit about the
mental model: a fixture parameter list works exactly like a test function's —
pytest resolves the whole graph before running anything.

```python
@pytest.fixture
def api_client():
    return TestAPIClient(base_url="http://testserver")

@pytest.fixture
def authenticated_client(api_client):
    token = api_client.post("/login", json={"user": "test"}).json()["token"]
    api_client.set_header("Authorization", f"Bearer {token}")
    return api_client

def test_get_profile(authenticated_client):
    resp = authenticated_client.get("/me")
    assert resp.status_code == 200
```

`test_get_profile` never has to know *how* authentication works — it asks for
`authenticated_client`, and the graph (`authenticated_client` → `api_client`)
resolves automatically. This is the mechanism that lets you build a small
number of low-level fixtures and compose higher-level, more specific ones
from them across a whole codebase, instead of every test file reinventing
setup from scratch.

## Concept: The Factory-as-Fixture Pattern

Sometimes a test needs *more than one* instance of something, or needs to
control specific attributes per-test — a plain fixture that returns one fixed
object can't do that. The fix is a fixture that returns a **function**
(a factory), so each test calls it with whatever arguments it needs:

```python
import pytest

@pytest.fixture
def make_user():
    created = []

    def _make_user(name="Test User", is_admin=False):
        user = User(name=name, is_admin=is_admin)
        created.append(user)
        return user

    yield _make_user

    for user in created:
        user.delete()   # cleanup every user this test created, however many

def test_admin_can_delete_regular_user(make_user):
    admin = make_user(is_admin=True)
    regular = make_user(name="Bob")
    assert admin.can_delete(regular)

def test_two_regular_users_cannot_delete_each_other(make_user):
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    assert not alice.can_delete(bob)
```

This is one of the highest-leverage patterns in this whole curriculum. It
gives you per-test flexibility (each call can pass different arguments)
*and* correct teardown (the fixture tracks everything it created and cleans
it all up), which a bare `return` fixture with hardcoded values can't do at
all, and a plain helper function (not a fixture) can't do safely, since it
has no hook into teardown.

## Concept: `conftest.py` Discovery and Layering

`conftest.py` files are auto-discovered by pytest — no import needed — and
their fixtures are available to every test **at or below** that directory:

```
project/
  conftest.py                 # fixtures available to ALL tests
  tests/
    conftest.py                # fixtures available to tests/ and below only
    unit/
      test_models.py           # sees fixtures from both conftest.py files
    integration/
      conftest.py               # fixtures available to integration/ only
      test_api.py               # sees fixtures from all three conftest.py files
```

Fixture *name resolution* follows a "closest wins" rule: if
`tests/integration/conftest.py` and the root `conftest.py` both define a
fixture named `db`, tests under `integration/` get the more specific one. This
is the mechanism for **fixture overriding** — a deliberate, common pattern:

```python
# tests/conftest.py
@pytest.fixture
def settings():
    return Settings(env="test")

# tests/integration/conftest.py
@pytest.fixture
def settings(settings):   # note: same name, requests the outer one too
    settings.external_api_enabled = True
    return settings
```

A fixture can even request another fixture *of the same name* from a wider
scope — pytest resolves this correctly, letting the narrower one wrap/extend
the broader one rather than fully replacing it. This is how large codebases
keep one canonical `settings`/`client`/`db` fixture name stable across the
whole suite while still letting specific subdirectories adjust it.

## Common Pitfalls

- **A factory fixture that doesn't track what it created.** If `make_user`
  doesn't append to `created` and clean up in teardown, every test that uses
  it leaks a user row/object, and you'll eventually hit unique-constraint
  failures or slow test databases bloated with garbage data.
- **Copy-pasting near-identical fixtures instead of composing or
  parametrizing.** If you see `user_admin`, `user_admin_inactive`,
  `user_admin_no_email` as three separate fixtures, that's usually a sign you
  want either a factory fixture or fixture parametrization (next lesson),
  not three hand-maintained near-duplicates that will drift out of sync.
- **Putting fixtures too high in the tree "just in case."** A fixture only
  relevant to `tests/integration/` that lives in the root `conftest.py`
  pollutes the fixture namespace for unit tests that don't need it, and (if
  autouse or expensive) can slow down unrelated tests. Put fixtures at the
  narrowest `conftest.py` that covers their real audience.
- **Not realizing fixture override requires matching the same fixture
  name deliberately.** If you rename a fixture in a nested `conftest.py`
  thinking you're "specializing" it, but the name doesn't match the outer
  one, you now have two unrelated fixtures and possibly confusing shadowing
  bugs depending on what else references the old name.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/04-composition-and-conftest/`, build a small multi-directory
> test project: a root `conftest.py` with a `session`-scoped `app_config`
> fixture, a `tests/unit/` directory with its own `conftest.py` defining a
> `make_order` factory fixture (an order has `items: list[str]` and a
> `status` defaulting to `"pending"`, with a `.cancel()` method that only
> works if status is `"pending"`), and a `tests/integration/conftest.py`
> that **overrides** `app_config` by requesting the outer `app_config`
> fixture and adding an extra attribute to it (e.g.
> `app_config.live_mode = True`). Write at least 4 tests across the two
> subdirectories that use `make_order` with different arguments per test
> (proving the factory pattern works), plus one test in `integration/` that
> asserts `app_config.live_mode is True` and one test in `unit/` that asserts
> the same attribute does NOT exist on `app_config` there (proving the
> override is scoped correctly and doesn't leak sideways). Leave the two
> `conftest.py` files under `unit/` and `integration/` for me to write from
> a docstring spec, with only the root `conftest.py` pre-written as a
> working example I can pattern-match from.

## Quiz

1. What problem does the factory-as-fixture pattern solve that a plain
   `return`-based fixture cannot?
2. In a factory fixture that creates multiple objects per test, why does
   teardown logic need to track *all* created objects in a list (or similar),
   rather than just cleaning up "the" object like a simple fixture would?
3. You have `conftest.py` files at the project root and at
   `tests/integration/`, both defining a fixture named `client`. Which one
   does a test inside `tests/integration/test_billing.py` receive, and what
   is this rule called informally?
4. Show (conceptually, no need for exact code) how a nested `conftest.py`
   fixture can *extend* rather than fully replace a same-named fixture from
   a parent `conftest.py`.
5. Why is putting a fixture in the root `conftest.py` "just in case it's
   useful later" a bad default, even though it costs nothing to define?

<details>
<summary>Answers</summary>

1. A plain fixture returns one fixed object, built once per test regardless
   of what the test actually needs. A factory fixture returns a *function*,
   so each test can call it multiple times with different arguments to get
   differently-configured instances on demand — something a single return
   value structurally cannot provide.
2. Because the fixture doesn't know in advance how many objects a given test
   will create — that's the whole point of exposing a factory. If teardown
   only cleaned up a single hardcoded object, any test that called the
   factory more than once would leak every object after the first,
   regardless of whether the fixture "looks fine" for tests that only call
   it once.
3. The test receives the fixture from `tests/integration/conftest.py` — the
   fixture defined closest to (at or below) the test file wins over one
   defined further up the tree. This is often called "closest fixture wins"
   or fixture shadowing/overriding.
4. The nested fixture is given the *same name* as the parent's fixture, and
   itself requests a parameter of that same name as an argument — pytest
   resolves this to mean "give me the parent-scope version of this fixture,"
   and the nested fixture can then mutate or wrap the value before returning
   it, rather than needing to reconstruct everything from scratch.
5. Every fixture defined at the root is visible (and, if `autouse`, applied)
   to the entire test suite, including unit tests that have nothing to do
   with it — this pollutes the shared fixture namespace, makes
   `conftest.py` harder to read for its actual intended audience, and (if
   the fixture has any real setup cost) can slow down or complicate tests
   that never needed it. Fixtures should live at the narrowest `conftest.py`
   that covers their real audience, and get promoted upward only when
   genuinely reused across sibling directories.

</details>

## Further Reading

- pytest docs — [conftest.py: sharing fixtures across multiple files](https://docs.pytest.org/en/stable/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files)
- pytest docs — [Factories as fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html#factories-as-fixtures)
- pytest docs — [Overriding fixtures on various levels](https://docs.pytest.org/en/stable/how-to/fixtures.html#overriding-fixtures-on-various-levels)

---
Previous: [03 — Fixture Scopes, Lifecycle & autouse](03-fixture-scopes-and-lifecycle.md) · Next: [05 — Parametrization Mastery](05-parametrization-mastery.md)
