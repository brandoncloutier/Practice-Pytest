# Lesson 03 — Fixture Scopes, Lifecycle & autouse

Phase 2: Fixtures & Parametrization Mastery

## Learning Objectives

- Name all five fixture scopes and correctly predict when each is torn down.
- Predict teardown *order* when multiple fixtures of different scopes are
  involved.
- Explain what `autouse=True` does, and articulate why it should be used
  sparingly.
- Diagnose state-leakage bugs caused by an overly-broad fixture scope.

## Why This Matters in Production

Scope is the single most common source of "why is this test flaky/slow/
order-dependent" bugs in real codebases. A `session`-scoped fixture that
should have been `function`-scoped silently shares mutable state across
hundreds of tests; a `function`-scoped fixture that should have been
`session`-scoped makes your suite reconnect to a test database 2,000 times
and turns a 10-second suite into a 4-minute one. Picking scope deliberately —
not just accepting the default — is a core production skill.

## Concept: The Five Scopes

```python
@pytest.fixture(scope="function")   # default if omitted
@pytest.fixture(scope="class")
@pytest.fixture(scope="module")
@pytest.fixture(scope="package")
@pytest.fixture(scope="session")
```

| Scope | Created | Destroyed |
|---|---|---|
| `function` | once per test function | at the end of that test |
| `class` | once per test class | after the last test in the class |
| `module` | once per test file | after the last test in the file |
| `package` | once per package (directory with `__init__.py`, or rootdir-relative test package) | after the last test in the package |
| `session` | once for the whole `pytest` run | at the very end of the run |

`function` is the safe default: no shared state, no surprises, but potentially
slow if setup is expensive. Widening the scope is an *optimization* you opt
into deliberately, trading isolation for speed — never the other way around.

```python
import pytest

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("postgresql://test-db/app_test")
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    """function-scoped: fresh transaction per test, rolled back after."""
    connection = db_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()
```

This is a canonical, production-realistic pattern: the *expensive, stateless*
part (`db_engine` — connecting to the database server at all) is
session-scoped, while the *cheap, must-be-isolated* part (`db_session` — the
actual data each test can see) is function-scoped and rolls back after every
test. You get speed and isolation simultaneously by scoping each concern
correctly instead of picking one scope for everything.

## Concept: Teardown Order

Two rules govern teardown order, and both matter once you're mixing scopes:

1. **Within a single yield fixture chain, teardown is LIFO** (reverse of
   setup). If test `t` depends on fixture `a`, which depends on fixture `b`,
   setup order is `b` then `a`; teardown order is `a` then `b` — "the
   right-most/most-recently-entered fixture tears down first."
2. **Higher (wider) scopes always outlive lower (narrower) scopes.** A
   `session`-scoped fixture that a `function`-scoped fixture depends on will
   not be torn down until the entire session ends, regardless of how many
   function-scoped fixtures came and went in between.

```python
@pytest.fixture(scope="session")
def session_fixture():
    print("SETUP session")
    yield
    print("TEARDOWN session")

@pytest.fixture
def function_fixture(session_fixture):
    print("SETUP function")
    yield
    print("TEARDOWN function")

def test_one(function_fixture):
    print("TEST ONE")

def test_two(function_fixture):
    print("TEST TWO")
```

Output order:
```
SETUP session
SETUP function
TEST ONE
TEARDOWN function
SETUP function
TEST TWO
TEARDOWN function
TEARDOWN session
```

`session_fixture` sets up once, stays alive across both tests, and tears down
last. This is worth running yourself with `pytest -s` — seeing it happen once
is worth more than reading the rule twice.

## Concept: `autouse=True`

Normally a fixture only runs if a test (or another fixture) explicitly
requests it by name. `autouse=True` makes a fixture apply to every test in
its scope **without being named**:

```python
@pytest.fixture(autouse=True)
def reset_global_registry():
    registry.clear()
    yield
    registry.clear()
```

This is legitimate for things like "always reset a piece of genuinely global
mutable state between tests" — but it's also the single easiest way to make a
test suite mysterious. A new engineer reading `def test_foo(client):` has no
textual signal that `reset_global_registry` is also running for that test.
Overusing `autouse` trades explicitness (a core pytest value — see how
fixtures are dependency-injected by name) for convenience, and it's easy to
end up with five different `autouse` fixtures across nested `conftest.py`
files whose combined interaction nobody can predict by reading a single test.

**Rule of thumb for production code:** reach for `autouse` only when the
behavior is genuinely universal for its scope (e.g., "every test in this
suite must run inside a fresh temp directory," "every test must have logging
captured at DEBUG") — not as a shortcut to avoid listing a fixture parameter.

## Common Pitfalls

- **Widening scope purely for speed and getting silent state leakage.**
  Session/module-scoped fixtures that return **mutable objects** (lists,
  dicts, ORM sessions with uncommitted state) let one test's mutation bleed
  into the next test that reuses the same instance. If you widen scope,
  either make the object immutable/stateless, or add function-scoped reset
  logic layered on top (like the `db_engine`/`db_session` split above).
- **Assuming test execution order is stable enough to rely on scope
  side-effects.** Don't write a `module`-scoped fixture assuming `test_a`
  always runs before `test_b` and sets something up for it — with
  `pytest-xdist` or `pytest-randomly` in the mix (common in production CI for
  speed and to catch order-dependence bugs), that assumption breaks.
- **Requesting a narrower-scoped fixture from a wider-scoped fixture.**
  pytest will raise a `ScopeMismatch` error — you cannot have a
  `session`-scoped fixture depend on a `function`-scoped one, because the
  wider-scoped fixture would need to be re-created within its own lifetime to
  keep up, which contradicts its own scope. The dependency direction only
  works wide-depends-on-narrow being *disallowed*, not the reverse.
- **Overusing `autouse` to "just make it work."** If you find yourself adding
  a fourth `autouse` fixture to a `conftest.py`, stop and ask whether an
  explicit fixture parameter (even if slightly repetitive across tests) would
  make the suite easier for the next person to reason about.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/03-fixture-scopes/`, build a deliberately broken example: a
> `session`-scoped fixture called `shared_cart` that returns a mutable
> `list` representing a shopping cart, used by three tests — the first two
> append items to it and assert on the cart's contents, and because the
> fixture is session-scoped, the third test unexpectedly sees leftover items
> from the first two and fails. Write the tests so this failure is visible
> when I run `pytest -v`. Then, in the same file, add a *second*, correctly
> isolated version using a `function`-scoped fixture that returns a fresh
> list, with three equivalent tests that all pass. Add a comment block
> at the top of the file summarizing the bug for after I've diagnosed it
> myself — but put it after a `"""SPOILER BELOW - try to explain the bug in
> a comment first before reading this"""` marker so I'm not tempted to peek.
> Also include a `print()`-based demonstration file
> (`test_teardown_order_demo.py`) with nested session/module/function
> fixtures like the one described in the fixture-scopes lesson, so I can run
> `pytest -s -v` and observe the actual teardown order rather than just
> reading about it.

## Quiz

1. You have `fixture_a` (session-scoped) and `fixture_b` (function-scoped),
   and `fixture_b` depends on `fixture_a`. In what order do they tear down,
   relative to each other, across a 10-test module?
2. Why would pytest raise an error if you tried to make a `session`-scoped
   fixture depend on a `function`-scoped one?
3. Give one legitimate production reason to use `scope="module"` instead of
   the `function` default, and one reason that scope choice could bite you
   later if the fixture's return value is mutable.
4. What is the main readability cost of `autouse=True`, independent of
   whether the fixture's *logic* is correct?
5. True or false: widening a fixture's scope is always safe as long as the
   fixture's setup code has no side effects on external systems.

<details>
<summary>Answers</summary>

1. `fixture_a` sets up once at the start and tears down once at the very
   end of the session — it outlives every instance of `fixture_b`.
   `fixture_b` sets up and tears down once per test (10 times total), always
   nested entirely inside `fixture_a`'s lifetime. Wider scopes always outlive
   narrower scopes they're depended on by.
2. Because a `session`-scoped fixture is only created once for the entire
   run, but a `function`-scoped dependency needs to be recreated for every
   test — satisfying both requirements at once is contradictory. pytest
   would have to either violate the session fixture's "created once"
   guarantee or give it a stale function-scoped value; instead it just
   raises `ScopeMismatch` at collection time so you fix the design.
3. Legitimate reason: an expensive-to-construct resource that's genuinely
   reusable and read-only across all tests in a file (e.g., parsing a large
   fixture JSON file once for a dozen read-only assertions). Risk: if that
   parsed object is a mutable structure (like a `dict` or `list`) and any
   test mutates it, later tests in the same module silently see the mutated
   version — a state-leak bug that's often intermittent-looking depending on
   test execution order.
4. It removes the textual signal from the test function's parameter list.
   Anyone reading `def test_checkout(client):` cannot tell, just from that
   line, that other fixtures are also running for this test — they have to
   go search `conftest.py` for anything marked `autouse=True` in scope. That
   costs real time during debugging and code review.
5. False. Even with zero external side effects, a widened scope shares one
   *instance* of the fixture's return value across many tests. If that value
   is mutable, one test's mutation is visible to the next test that reuses
   the same cached instance — purely an in-process state-leak risk,
   independent of anything external.

</details>

## Further Reading

- pytest docs — [Fixture finalization / executing teardown code](https://docs.pytest.org/en/stable/how-to/fixtures.html#teardown-cleanup-aka-fixture-finalization)
- pytest docs — [Fixture scopes](https://docs.pytest.org/en/stable/how-to/fixtures.html#fixture-scopes)
- pytest docs — [Autouse fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html#autouse-fixtures-fixtures-you-don-t-have-to-request)

---
Previous: [02 — Fixtures 101](02-fixtures-101.md) · Next: [04 — Fixture Composition, Factories & conftest.py](04-fixture-composition-and-conftest.md)
