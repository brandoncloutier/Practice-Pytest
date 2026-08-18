# Lesson 02 — Fixtures 101

Phase 1: Foundations Refresher

## Learning Objectives

- Define what a pytest fixture is, precisely (not "setup code").
- Use `yield` fixtures for setup/teardown instead of `unittest`-style
  `setUp`/`tearDown`.
- Use the `request` fixture to introspect the test requesting a fixture.
- Explain why fixtures are **dependency-injected**, and why that's a
  meaningfully different design from xUnit-style setup methods.

## Why This Matters in Production

If you learned pytest coming from `unittest`, you may still be writing
`setUp`/`tearDown` methods inside `TestCase` classes out of habit, or
duplicating setup logic across test functions with copy-pasted helper calls.
Fixtures are pytest's actual answer to test setup, and they compose in ways
`setUp` fundamentally can't (that's Lessons 03–04). Getting comfortable with
plain fixtures now is the prerequisite for everything else in Phase 2 and 3 —
`mocker`, `monkeypatch`, `tmp_path`, and every other built-in tool you already
use *are themselves* just fixtures. Understanding fixtures means understanding
how those tools work, not just that they work.

## Concept: A Fixture Is a Function pytest Calls for You

A fixture is a function decorated with `@pytest.fixture`. Any test function
(or fixture) that has a parameter with the same name as the fixture will have
that fixture **called on its behalf**, and receive its return value.

```python
import pytest

@pytest.fixture
def sample_user():
    return {"id": 1, "name": "Ada Lovelace"}

def test_user_has_name(sample_user):
    assert sample_user["name"] == "Ada Lovelace"
```

Nothing calls `sample_user()` explicitly. pytest sees the test function's
parameter list, matches `sample_user` to the fixture of that name, calls it,
and passes the result in. This is **dependency injection**: the test declares
what it needs by name, and pytest is responsible for constructing it. Compare
this to `unittest.TestCase.setUp`, which runs unconditionally for *every* test
in the class whether that test needs the setup or not, and can only build one
undifferentiated blob of `self.foo` state.

## Concept: `yield` Fixtures for Setup and Teardown

A fixture that only needs to `return` a value is common, but many fixtures
need to clean up after themselves — closing a file, rolling back a
transaction, closing a network connection. Use `yield` instead of `return`;
code after the `yield` runs as teardown, guaranteed to run even if the test
fails:

```python
import pytest

@pytest.fixture
def temp_log_file(tmp_path):
    path = tmp_path / "app.log"
    handle = path.open("w")
    yield handle          # test runs here, using `handle`
    handle.close()         # teardown — runs even if the test raises
```

The guarantee that teardown runs on failure is the whole point. If you
instead wrote setup and cleanup as two separate helper functions called
manually inside the test body, an assertion failure partway through would
skip the cleanup call — a classic source of test pollution, where one test's
leftover state breaks a later, unrelated test.

You can also register cleanup imperatively via `request.addfinalizer()` (you
saw this mentioned in fixture teardown ordering) but `yield` is preferred in
modern code — it's more readable and you can only forget it once before the
lesson sticks.

## Concept: The `request` Fixture

`request` is a special built-in fixture that gives a fixture function
information about the test (or fixture) that's requesting it:

```python
import pytest

@pytest.fixture
def db_connection(request):
    print(f"Setting up DB connection for {request.node.name}")
    conn = connect_to_test_db()
    yield conn
    conn.close()
```

`request.node.name` is the name of the requesting test. `request.param` is
how parametrized fixtures receive their parameter (Lesson 05).
`request.module`, `request.cls`, `request.fixturenames` and others give you
even more introspection. You won't use `request` in every fixture, but it's
the escape hatch for "this fixture needs to behave differently depending on
context" — and you'll meet it again heavily in Lessons 03–05.

## Concept: Fixtures Are Composable (Preview)

A fixture can itself request other fixtures as parameters, and pytest
resolves the whole dependency graph for you:

```python
@pytest.fixture
def db_connection():
    conn = connect_to_test_db()
    yield conn
    conn.close()

@pytest.fixture
def seeded_db(db_connection):
    db_connection.execute("INSERT INTO users VALUES (1, 'Ada')")
    return db_connection

def test_user_lookup(seeded_db):
    assert seeded_db.query("users", id=1) is not None
```

`test_user_lookup` never mentions `db_connection` directly — it asks for
`seeded_db`, which asks for `db_connection`, and pytest wires the whole chain
together, respecting teardown order automatically. This composability is the
core reason fixtures scale better than `setUp` as a suite grows; Lesson 04
goes deep on this pattern.

## Common Pitfalls

- **Using `return` when you need cleanup.** If a fixture opens a resource and
  never yields+closes it, you get resource leaks across a long test run —
  often invisible until the suite is large enough to exhaust file handles or
  connections.
- **Putting assertions inside a fixture.** Fixtures set up state; they
  shouldn't be where you check correctness. If a fixture's own setup can
  fail, that's fine (it'll show as an error, per Lesson 01) — but assertions
  about the *behavior under test* belong in the test function.
- **Forgetting a fixture teardown can itself raise.** If teardown code
  raises, pytest reports it, but it can mask the original test failure's
  clarity — keep teardown simple and let it fail loudly only for real bugs
  (e.g., an unclosed transaction failing to roll back is worth knowing about).
- **Reaching for a fixture when a plain helper function would do.** Not
  everything needs to be a fixture. If there's no setup/teardown lifecycle
  and no dependency injection benefit, a plain function (or even a
  module-level constant) is simpler and easier to read than a fixture with a
  weird name collision waiting to happen.

## Exercise Prompt (hand this to Claude Code)

> Scaffold `exercises/02-fixtures-101/` with a small `src/notifier.py` module
> that has a `Notifier` class wrapping a fake outbound "mail client" object
> (just an in-memory object with a `.sent` list — no real network calls).
> Then write `tests/test_notifier.py` where I practice writing fixtures
> myself: give me the `Notifier` class and a bare-bones fake mail client, but
> leave the *fixtures* as TODOs with docstrings describing what each should
> do (e.g. "TODO: write a yield-fixture called `notifier` that constructs a
> `Notifier` with a fresh fake mail client, and after the test runs, asserts
> the fake mail client's connection was 'closed' — add a `.closed` flag to
> the fake client that the fixture sets in teardown"). I want to write the
> fixture bodies myself, not have them generated. Include at least one test
> that uses `request.node.name` inside a fixture to prove I understand how
> `request` works.

## Quiz

1. In your own words: what does "dependency injection" mean in the specific
   context of a pytest fixture parameter?
2. Why is a `yield` fixture safer than manually calling setup and cleanup
   helper functions inside each test body?
3. What does `request.node.name` give you inside a fixture, and name one
   realistic reason you'd want it?
4. True or false, with justification: "Every setup step in a test file should
   be turned into a fixture."
5. A fixture opens a database connection with `return conn` (no yield, no
   explicit close anywhere). Is the connection guaranteed to be closed after
   each test? Why or why not?

<details>
<summary>Answers</summary>

1. It means the test function doesn't construct what it depends on itself —
   it declares the dependency by naming a parameter, and pytest looks up the
   matching fixture, resolves and calls it (and anything *it* depends on),
   and hands the result to the test. The test is decoupled from *how* the
   dependency is built.
2. Because the code after `yield` is guaranteed to run during teardown even
   if the test body raises an assertion error or exception — pytest treats
   it like a `finally` block. Manually-called cleanup helpers get skipped if
   an earlier assertion in the test fails, which can leak state into later
   tests.
3. It gives you the name of the test (or fixture) currently requesting this
   fixture. A realistic use: logging/debugging output during setup that's
   tagged with which test triggered it, or branching fixture behavior based
   on markers/attributes of the requesting test via other `request`
   attributes.
4. False. Fixtures are worth it when there's a setup/teardown lifecycle to
   manage, or when dependency injection/reuse across multiple tests adds
   value. A one-off local variable or a simple helper function used by a
   single test doesn't need the ceremony of a fixture — over-using fixtures
   for everything makes tests harder to read, not easier.
5. No. Nothing closes it. `return` just gives the test the connection object;
   there's no teardown code because there's no `yield` for code to run after.
   Without a `yield` + explicit close (or `request.addfinalizer`), the
   connection lives until Python's garbage collector happens to clean it up
   — not a guarantee, and a common source of connection leaks in real test
   suites.

</details>

## Further Reading

- pytest docs — [About fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html)
- pytest docs — [How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html)

---
Previous: [01 — The pytest Mental Model](01-the-pytest-mental-model.md) · Next: [03 — Fixture Scopes, Lifecycle & autouse](03-fixture-scopes-and-lifecycle.md)
