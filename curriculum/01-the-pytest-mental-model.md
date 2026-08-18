# Lesson 01 — The pytest Mental Model

Phase 1: Foundations Refresher

## Learning Objectives

By the end of this lesson you will be able to:

- Explain how pytest *discovers* tests without you registering them anywhere.
- Explain why plain `assert` statements work in pytest but give useless
  output in plain Python — and what "assertion rewriting" actually does.
- Read and interpret pytest's exit codes in a script or CI step.
- Explain the difference between a test **failure** and a test **error**.
- Describe what `pytest.ini` / `pyproject.toml` / `conftest.py` each are
  responsible for, at a high level (later lessons go deep on `conftest.py`).

## Why This Matters in Production

Most engineers learn pytest by imitation: they copy a test file that already
exists, change the names, and it works. That's fine until something *doesn't*
work — a test silently doesn't run, an import fails and gets reported as a
"test," or CI reports a different exit code than you expect and a deploy gate
does the wrong thing. When that happens, you need the actual model, not the
folklore. This lesson is the folklore-removal pass.

## Concept: Test Discovery

pytest doesn't require you to register tests in a suite object. Instead, it
**collects** them by walking the filesystem and applying naming conventions:

- Files: `test_*.py` or `*_test.py`
- Classes: `Test*` (and — important gotcha — the class must have **no
  `__init__` method**, or pytest will skip it with a warning, since pytest
  needs to instantiate it itself)
- Functions/methods: `test_*`

This is configurable (`python_files`, `python_classes`, `python_functions` in
your config), but the defaults above are what you'll see in the overwhelming
majority of codebases, including most production ones. If a test "isn't
running" and you don't get an error, naming convention mismatch is the first
thing to check — pytest collected zero items and reported success trivially.

```python
# test_math_ops.py

def test_addition():                 # collected: matches test_*
    assert 1 + 1 == 2

def add_two_numbers_test():          # NOT collected: doesn't start with test_
    assert 1 + 1 == 2

class TestCalculator:                # collected: matches Test*, no __init__
    def test_subtract(self):         # collected: method matches test_*
        assert 5 - 3 == 2
```

Run `pytest --collect-only` regularly — it's the single best debugging tool
for "why didn't my test run," because it shows you exactly what pytest thinks
exists before it runs anything.

## Concept: Assertion Rewriting

In plain Python, `assert 1 + 1 == 3` raises `AssertionError` with **no
message** unless you write one yourself (`assert x == y, f"{x} != {y}"`).
That's why bare `assert` is usually considered too weak to build a test
framework on.

pytest gets around this without asking you to write custom messages, because
it doesn't run your test file as plain Python. At collection time, pytest's
import hook rewrites the AST (abstract syntax tree) of test modules, replacing
bare `assert` statements with versions that capture the intermediate values
of the expression and build a detailed failure message automatically. This is
why:

```python
def test_user_count():
    users = ["alice", "bob"]
    assert len(users) == 3
```

fails with something like:

```
    def test_user_count():
        users = ["alice", "bob"]
>       assert len(users) == 3
E       assert 2 == 3
E        +  where 2 = len(['alice', 'bob'])
```

instead of just `AssertionError`. This only happens for files pytest actually
collects as test modules through its import machinery — it's why third-party
assertion helper libraries exist (`assertpy`, etc.) but are rarely needed, and
why bare `assert` is the idiomatic, encouraged style in pytest, unlike in
`unittest` where you reach for `self.assertEqual(a, b)`.

**Production implication:** if you see a test failure with no rewritten
diff — just a bare `AssertionError` — it usually means the assertion happened
inside code pytest didn't rewrite (e.g., a helper function imported from a
non-test module, or an assertion inside a thread/subprocess). That's a signal
to move the assertion back into the test function itself, or accept you'll
need a manual message.

## Concept: Failures vs. Errors

pytest distinguishes:

- **Failure (`F`)** — the test ran to completion and an assertion (or
  `pytest.fail()`) triggered.
- **Error (`E`)** — something went wrong *outside* the test body itself:
  a fixture raised an exception during setup, collection failed (e.g. an
  import error in the test file), or teardown raised.

This distinction matters operationally: a wave of `E`rrors after a dependency
bump usually means an import is broken or a fixture is misconfigured — not
that your code regressed. Triage errors before failures; they often explain
away a large chunk of a red CI run in one fix.

## Concept: Exit Codes

pytest returns a process exit code, which matters when it's gating a CI
pipeline or a pre-commit hook:

| Code | Meaning |
|---|---|
| 0 | All tests passed |
| 1 | Tests were collected and ran, but some failed |
| 2 | Test execution was interrupted (e.g. Ctrl-C) |
| 3 | Internal error in pytest |
| 4 | pytest command-line usage error |
| 5 | No tests were collected |

Code **5** is the one people forget about. A CI job that's supposed to run
tests but has a broken path/glob will often report "success" if you only
check `exit code == 0` naively in some setups, or fail confusingly in others —
knowing that 5 exists (and asserting on it, or at minimum reading pytest's own
summary line) is how you catch a suite that quietly stopped running.

## Concept: Where Configuration Lives

You'll see three files doing overlapping-looking jobs; here's the division:

- **`pyproject.toml`** (`[tool.pytest.ini_options]`) — the modern, preferred
  place for pytest configuration (markers, testpaths, addopts, etc.) if the
  project already uses `pyproject.toml` for packaging. Most new projects.
- **`pytest.ini`** — a dedicated file for the same configuration, used when a
  project doesn't want pytest config mixed into `pyproject.toml`, or predates
  its adoption.
- **`conftest.py`** — not configuration in the ini sense at all. It's a
  regular Python file pytest auto-imports, used for **fixtures, hooks, and
  plugins local to a directory tree**. You'll go deep on this in Lesson 04.

A common early confusion: "why is this fixture available in every test file
without an import?" — that's `conftest.py` doing its job. Nothing is
imported explicitly; pytest discovers `conftest.py` files up the directory
tree from each test file and makes their fixtures ambiently available.

## Common Pitfalls

- **Assuming a silently-empty test run is a passing run.** Always glance at
  the summary line (`collected N items`) — 0 collected is not the same as 0
  failed, and both look "green-ish" if you're not paying attention.
- **Naming a helper function `test_helper()` or a fixture-only class
  `TestConfig`.** pytest will try to collect it, and either fail confusingly
  or emit a `PytestCollectionWarning` about a class with an `__init__`.
- **Writing assertions inside a non-test helper module and being surprised
  by an unhelpful `AssertionError` with no diff.** Assertion rewriting is
  scoped to files pytest imports as test modules.
- **Treating exit code 5 (no tests collected) the same as exit code 0.**
  In CI, a broken `testpaths` glob can produce a "successful," useless run.

## Exercise Prompt (hand this to Claude Code)

> Set up a small pytest project under `exercises/01-mental-model/`. Create a
> `src/inventory.py` module with a couple of small pure functions (e.g.
> `total_price(items)`, `apply_discount(price, percent)`) with at least one
> deliberate edge case (like negative discount) left unhandled. Then create
> a `tests/test_inventory.py` with a mix of: (a) a test that passes, (b) a
> test that fails on a plain equality assertion so I can see the rewritten
> assertion diff, (c) one test file that has a naming typo
> (`shipping_test_extra.py` with functions named `check_*` instead of
> `test_*`) so I can practice noticing pytest silently not collecting it, and
> (d) a fixture in `conftest.py` that raises an exception during setup for
> one specific test, so I can see an **error** (`E`) instead of a
> **failure** (`F`) in the output. Do not fix the typo or the fixture bug for
> me — I want to diagnose them myself using `pytest --collect-only -v` and
> reading the summary line.

## Quiz

1. You run `pytest` and see `collected 0 items` with exit code 5. Your
   teammate says "tests passed, it's green." What's wrong with that claim?
2. Why does `assert x == y` give you a useful diff in a pytest test file but
   just `AssertionError` with no detail if you run the same line in a plain
   Python REPL?
3. A fixture used by `test_checkout` raises a `ConnectionError` during setup.
   In the pytest summary, will this show up as a failure (`F`) or an error
   (`E`), and why does the distinction matter when triaging a red CI run?
4. You define `class TestUtils` in a test file to hold some shared helper
   methods, and give it an `__init__` to store some setup state. What will
   pytest do, and why?
5. What's the practical difference between `pytest.ini` and
   `conftest.py` — could you replace fixtures defined in `conftest.py` by
   just putting them in `pytest.ini` instead?

<details>
<summary>Answers</summary>

1. Exit code 5 means **no tests were collected at all** — it is not the same
   as "0 tests failed." The run is not exercising any code; a broken
   `testpaths`/glob, a naming convention mismatch, or an empty directory can
   all produce this. It should be treated as a failure of the CI job, not a
   pass.
2. pytest rewrites the AST of assert statements in files it collects as test
   modules, capturing the intermediate values of the expression to build a
   detailed message. A plain REPL (or any code pytest didn't import through
   its collection machinery) just gets Python's default `assert` behavior,
   which raises `AssertionError` with no message unless you supply one.
3. It shows up as an **error (`E`)**, because the exception happened during
   fixture setup, not inside the test body's assertions. The distinction
   matters because a wave of errors after, say, a dependency bump usually
   points to one root cause (a broken fixture/import), whereas a wave of
   failures usually means many different assertions are wrong — you triage
   and prioritize them differently.
4. pytest will refuse to collect it as a test class (or emit a
   `PytestCollectionWarning`) because pytest needs to instantiate test
   classes itself with no arguments, and a custom `__init__` breaks that
   contract. Any `test_*` methods inside it will silently not run.
5. `pytest.ini` (and the `pyproject.toml` equivalent) is for **configuration
   options** — key/value settings like `testpaths`, `markers`, `addopts`.
   `conftest.py` is a **Python module** pytest auto-imports per-directory to
   supply fixtures, hooks, and local plugin code. You cannot replace fixtures
   with ini settings — fixtures are code (they can compute values, make
   network calls, manage teardown), and ini files can't express that.

</details>

## Further Reading

- pytest docs — [How to invoke pytest](https://docs.pytest.org/en/stable/how-to/usage.html)
- pytest docs — [Good Integration Practices (test discovery rules)](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- pytest docs — [Writing and reporting assertions in tests](https://docs.pytest.org/en/stable/how-to/assert.html)

---
Next: [02 — Fixtures 101](02-fixtures-101.md)
