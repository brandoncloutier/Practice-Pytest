# Lesson 12 — Markers & Test Selection

Phase 4: Production Test Design

## Learning Objectives

- Use built-in markers: `skip`, `skipif`, `xfail`, `parametrize` (already
  covered — this lesson focuses on the other three).
- Register and use custom markers, and understand why unregistered markers
  produce warnings.
- Select test subsets with `-k` (name/keyword expressions) and `-m`
  (marker expressions) confidently.
- Distinguish `xfail` from `skip`, and explain the `strict` option's
  purpose.

## Why This Matters in Production

As a suite grows into the thousands of tests, "run everything, every time,
everywhere" stops being free. Some tests are slow (hit a real database
container), some are environment-specific (require a GPU, require network
access disabled in CI, require credentials only present in one pipeline
stage), and some are known-broken pending a fix that isn't ready yet. Markers
and selection expressions are how you express these distinctions to pytest
itself, instead of commenting tests out, deleting them, or maintaining a
separate ad hoc list of "tests to skip" somewhere outside the test suite.

## Concept: `skip` and `skipif`

```python
import sys
import pytest

@pytest.mark.skip(reason="not implemented yet, tracked in JIRA-4021")
def test_bulk_export():
    ...

@pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX-only os.fork")
def test_worker_fork_behavior():
    ...
```

`skip` unconditionally skips; `skipif` takes a boolean condition evaluated at
collection time. **Always supply `reason=`** — an unexplained skip is a
future maintenance trap: six months later nobody remembers why, and nobody
feels safe removing the marker either. A skip without a reason is a test
quietly rotting.

You can also skip imperatively from inside a test body — useful when the
decision depends on something only known once the test starts running:

```python
def test_requires_external_service():
    if not external_service_is_reachable():
        pytest.skip("external service not reachable in this environment")
    ...
```

## Concept: `xfail`

`xfail` ("expected failure") marks a test that's *known* to fail right now —
different from `skip` in an important way: **`xfail` still runs the test.**
If it fails, it's reported as `XFAIL` (expected, not a suite-breaking
failure). If it unexpectedly *passes*, it's reported as `XPASS`.

```python
@pytest.mark.xfail(reason="rounding bug in legacy calculator, JIRA-889")
def test_legacy_calculator_rounds_correctly():
    assert legacy_calculate(0.1, 0.2) == 0.3
```

The `strict` parameter changes what happens on `XPASS`:

```python
@pytest.mark.xfail(reason="...", strict=True)
def test_something():
    ...
```

With `strict=True`, an unexpected pass (`XPASS`) is treated as a **suite
failure** — the point being: if a test marked "known broken" starts passing,
that's worth noticing and consciously removing the marker for, not silently
absorbing forever. Without `strict` (the non-strict default historically,
though modern pytest lets you configure the default via `xfail_strict` in
config), an `XPASS` is just reported, not treated as a failure — meaning a
fixed bug's test can stay marked `xfail` indefinitely without anyone
noticing it no longer needs to be. **Production guidance: prefer
`strict=True`** (or set `xfail_strict = true` project-wide in config) so
`xfail` markers actively get cleaned up as bugs get fixed, rather than
accumulating as permanent, invisible technical debt.

`skip` vs `xfail`, summarized: use `skip` when running the test is pointless
or impossible right now (wrong platform, missing dependency, not yet
implemented). Use `xfail` when the test is meaningful, runnable, and
documents a *known, currently-true* bug you want tracked and automatically
flagged the moment it's fixed.

## Concept: Custom Markers

```python
# in a test file
@pytest.mark.slow
def test_full_data_pipeline():
    ...

@pytest.mark.integration
def test_real_database_round_trip():
    ...
```

Custom markers need to be **registered** (in `pyproject.toml` or
`pytest.ini`) or pytest emits a `PytestUnknownMarkWarning` — a deliberate
guardrail against silent typos (`@pytest.mark.slwo` instead of `@pytest.
mark.slow` produces no error otherwise, and your `-m slow` selection quietly
misses that test forever):

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests that hit real external systems",
]
```

Registering markers with a description also makes `pytest --markers` a
genuinely useful, self-documenting reference for what selection categories
exist in a given codebase — worth checking before you invent a new marker
name that's really a duplicate of an existing convention.

## Concept: Selecting Subsets — `-k` and `-m`

```bash
pytest -m slow                    # run only tests marked @pytest.mark.slow
pytest -m "not slow"              # run everything EXCEPT slow tests
pytest -m "integration and not slow"   # boolean expressions over markers

pytest -k "checkout"              # run tests whose name contains "checkout"
pytest -k "checkout and not refund"    # combine keyword expressions
pytest -k "test_price_formatting[EUR-10]"   # target one specific parametrize case
```

`-m` filters by marker; `-k` filters by substring match against test (and
class/module) names, including generated parametrize IDs — which is exactly
why Lesson 05's advice to give parametrize cases explicit, readable `id=`
values pays off directly here: `-k "missing-name"` only works cleanly if
that string actually appears in the test ID.

A common production CI pattern: a fast default run (`pytest -m "not slow and
not integration"`) on every push, and a separate, less frequent pipeline
stage running the full suite or specifically `-m integration` against real
infrastructure — trading immediate feedback speed against full coverage
deliberately, rather than accepting one blanket policy for every situation.

## Common Pitfalls

- **Skipping without a reason.** `@pytest.mark.skip` with no `reason=`
  leaves no trail for why — always supply one, ideally with a ticket
  reference if there's follow-up work implied.
- **Using `skip` for a test that's actually documenting a known bug.**
  That's what `xfail` is for — `skip` prevents the test from running at
  all, so it can never tell you when the bug gets fixed.
- **Never setting `strict=True` (or `xfail_strict` project-wide) on
  `xfail`.** Non-strict `xfail` markers accumulate silently as bugs get
  fixed elsewhere, becoming permanent, stale technical debt in the test
  suite itself.
- **Using an unregistered custom marker.** Beyond the warning noise, a typo
  in a marker name (`@pytest.mark.slwo`) silently creates a *new*,
  effectively empty marker category — `-m slow` won't select that test, and
  nothing tells you why until you go looking.
- **Overusing `-k` string matching for what should be a marker.** If you're
  regularly running `pytest -k "not test_slow_thing_one and not
  test_slow_thing_two and not ..."`, that's a sign those tests should share
  a `@pytest.mark.slow` marker instead of an ever-growing manual exclusion
  list.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/12-markers-and-selection/`, set up a `pyproject.toml` in
> that folder registering two custom markers, `slow` and `integration`, with
> descriptions, and set `xfail_strict = true` in the pytest config section.
> Then create `tests/test_reporting.py` with at least 8 tests covering: two
> plain fast tests with no markers; two tests marked `@pytest.mark.slow`
> (have them literally call `time.sleep(0.5)` so the slowness is real and
> measurable, not just labeled); two tests marked `@pytest.mark.integration`
> that would need a real network call (fake this with a `pytest.skip(...)`
> imperative check inside the test body simulating "external service not
> reachable" so they skip cleanly in this sandbox instead of actually
> calling the network); one `@pytest.mark.xfail(reason=..., strict=True)`
> test that genuinely fails right now (a real, small bug in a helper
> function you also create in `src/`); and one `@pytest.mark.skipif` test
> gated on `sys.version_info` in some way, with a clear reason. After
> writing them, show me the exact `pytest -m` and `pytest -k` invocations
> (as a comment block at the top of the test file, not run automatically)
> that would: run only the fast, non-slow, non-integration tests; run only
> `slow` tests; run everything except `integration` tests; and target just
> the one `xfail` test by name. I'll run these myself to confirm the
> selection behaves as predicted.

## Quiz

1. Your teammate skips a test with `@pytest.mark.skip` and no `reason`.
   Six months later, should you feel comfortable deleting the test or the
   marker? Why does this lesson push for always including a reason?
2. A test is marked `xfail` (non-strict) documenting a bug. The bug gets
   fixed in a later PR, but nobody removes the marker. What does the test
   suite report going forward, and why is that a problem `strict=True`
   would have caught?
3. What's the concrete difference in whether the test body actually
   executes, between `skip` and `xfail`?
4. Why does pytest warn on unregistered custom markers instead of just
   silently allowing any `@pytest.mark.whatever`?
5. You want CI to run everything except tests marked `slow` or
   `integration` on every push. Write the `-m` expression for that.

<details>
<summary>Answers</summary>

1. No — without a reason, there's no way to know whether the skip is safe to
   remove (the underlying issue was fixed), still necessary (still broken or
   still environment-specific), or was accidental. A reason (ideally with a
   ticket reference) gives future maintainers — including the original
   author, later — the context needed to make that call instead of guessing
   or leaving it skipped indefinitely out of caution.
2. It reports `XPASS` — an unexpected pass — for that test, on every run,
   going forward. Without `strict=True`, `XPASS` is typically not treated as
   a failure, so nothing forces anyone to notice or act on it; the marker
   becomes permanent, misleading technical debt implying a bug still exists
   when it doesn't. With `strict=True`, that same `XPASS` is treated as a
   suite failure, forcing someone to notice and remove the now-unnecessary
   marker.
3. `skip` prevents the test body from executing at all — it's not run,
   period. `xfail` still runs the test body; the difference is purely in how
   the *outcome* is interpreted and reported (a failure becomes `XFAIL`
   instead of a red failure, and a pass becomes `XPASS`).
4. To catch typos and prevent silent, effectively-empty marker categories.
   Without registration, `@pytest.mark.slwo` (a typo of `slow`) would create
   a new, valid-looking marker that simply never gets selected by `-m slow`
   — with no warning that anything is wrong, since Python attribute access
   on `pytest.mark` doesn't validate the name against anything by default.
5. `pytest -m "not slow and not integration"`

</details>

## Further Reading

- pytest docs — [How to mark test functions with attributes](https://docs.pytest.org/en/stable/how-to/mark.html)
- pytest docs — [Skip and xfail: dealing with tests that cannot succeed](https://docs.pytest.org/en/stable/how-to/skipping.html)
- pytest docs — [Registering marks](https://docs.pytest.org/en/stable/how-to/mark.html#registering-marks)

---
Previous: [11 — Exceptions, Warnings & Logging](11-exceptions-warnings-and-logging.md) · Next: [13 — Test Organization at Scale](13-test-organization-at-scale.md)
