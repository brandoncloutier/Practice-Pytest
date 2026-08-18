# Lesson 19 — CI/CD Integration & Tooling

Phase 6: Team & Pipeline Practices

## Learning Objectives

- Configure pytest via `pyproject.toml`, and know what belongs there versus
  in `conftest.py` (revisiting Lesson 01 with more depth).
- Use `pytest-xdist` to parallelize a suite, and understand the tradeoffs
  it introduces.
- Structure a CI pipeline with staged test runs (fast/unit first, slower
  integration later) rather than one monolithic run.
- Explain what `tox`/`nox` add over "just run pytest in CI directly."

## Why This Matters in Production

A test suite that takes 45 minutes in CI doesn't just cost 45 minutes — it
costs however many times per day every engineer waits on it, multiplied
across the team, plus the context-switching cost of "I'll check back later."
This lesson is about the concrete tools and pipeline structure that keep a
growing suite fast and trustworthy as it scales, rather than accepting
"tests are slow" as an inevitability.

## Concept: Configuration in `pyproject.toml`

```toml
[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests that hit real external systems",
]
xfail_strict = true
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:some_noisy_dependency.*",
]
```

Worth calling out a few options specifically, because they're high-value
and easy to miss:

- **`--strict-markers`** — makes an unregistered marker (Lesson 12) an
  **error** instead of just a warning, which is the stronger, CI-appropriate
  version of that guardrail — a typo'd marker fails the build loudly instead
  of silently producing a warning easy to miss in a long CI log.
- **`--strict-config`** — errors on unknown/misspelled config options in
  the ini section itself, catching typos in the config file the same way
  `--strict-markers` catches typos in marker names.
- **`xfail_strict = true`** — sets the project-wide default discussed in
  Lesson 12, so every `xfail` is strict unless a specific test opts out.
- **`filterwarnings = ["error", ...]`** — promotes warnings to errors by
  default, forcing your own code's warnings (and often a useful subset of
  dependencies') to be dealt with rather than silently accumulating in test
  output nobody reads — combined with targeted `ignore::` entries for
  specific known-noisy dependencies you don't control.
- **`testpaths`** — tells pytest where to look without needing it passed
  on the command line every time, and (tying back to Lesson 01) makes a
  broken/empty `testpaths` glob a visible, fixable configuration fact rather
  than a mysterious "why did it collect 0 items" surprise.

## Concept: Parallelization with `pytest-xdist`

```bash
pip install pytest-xdist
pytest -n auto      # spawn one worker process per available CPU core
pytest -n 4          # explicit worker count
```

`pytest-xdist` distributes tests across multiple worker processes, running
them concurrently — often a large, direct speedup for CPU-bound or
I/O-wait-heavy suites. It's also, not incidentally, one of the best tools
available for **surfacing hidden test interdependence** (Lesson 13): tests
that only pass because of assumed execution order or shared mutable state
will often fail intermittently, or fail consistently but in a way that's
different from a sequential run, under `xdist`'s parallel/distributed
execution — a real, useful signal that a suite has a design problem worth
fixing, not just an `xdist` compatibility problem to work around.

The corresponding cost: worker processes are separate Python processes, so
truly global state assumptions (a single shared temp file, a single shared
in-memory cache in the test process itself) don't automatically hold across
workers the way they would sequentially — test isolation (session-scoped
fixtures, database setup) needs to be genuinely safe for concurrent,
multi-process execution, not just "works when run one after another."

## Concept: Staged Pipelines

A common, effective structure for CI, applying Lesson 12's marker-based
selection directly to pipeline design:

```yaml
# conceptual, not tied to a specific CI vendor's exact syntax
stages:
  - name: fast-checks
    run: pytest -m "not slow and not integration" -n auto
    # runs on every push, blocks merge, target: seconds to low minutes

  - name: full-suite
    run: pytest -m "not integration" -n auto --cov=src --cov-fail-under=85
    # runs on every push to main / on PR-ready, slightly slower

  - name: integration
    run: pytest -m integration
    # runs on a schedule, or before deploy, against real dependencies
```

The principle: **fast, deterministic feedback should never wait behind
slow, occasionally-flaky feedback.** An engineer pushing a small change
should see the fast-checks result in the time it takes to context-switch to
something else, not in the time it takes a full integration suite hitting
real external systems to complete. This is exactly why Lesson 12's marker
discipline matters operationally, not just organizationally — the pipeline
stages above are only possible because `slow` and `integration` are
reliably, consistently applied markers across the whole suite.

## Concept: What `tox`/`nox` Add

`tox` (and its more Python-scriptable cousin, `nox`) automate running your
test suite across **multiple isolated environments** — different Python
versions, different dependency version combinations, different optional
extras — each in its own virtual environment, defined declaratively:

```ini
# tox.ini
[tox]
envlist = py310, py311, py312, py313

[testenv]
deps = pytest pytest-cov
commands = pytest --cov=src
```

Running `tox` locally or in CI executes the suite once per configured
environment, catching version-specific breakage (a feature that only exists
in Python 3.12+, a dependency behaving differently across two supported
Python versions) that a single "just run pytest" CI job — pinned to one
Python version — would never surface. This matters specifically for
libraries and tools that need to support a range of Python/dependency
versions in production; it matters less for an internal application
service deployed to one controlled runtime, where a single pinned
environment is often the more appropriate choice. Know which situation your
project is in before reaching for `tox`/`nox` by default.

## Common Pitfalls

- **One monolithic `pytest` CI step running everything, every time.**
  Works fine at 50 tests; becomes a genuine velocity tax at 5,000 — stage
  the pipeline deliberately using markers, per above.
- **Not using `--strict-markers`/`--strict-config`**, letting typos in
  marker names or config options fail silently (a warning in a long CI log
  nobody reads) instead of loudly (a build error that has to be fixed
  before merge).
- **Assuming `pytest-xdist` parallelization is "free" speed with zero
  design implications**, then being surprised by intermittent failures that
  are actually pre-existing test interdependence bugs the sequential run
  never happened to expose.
- **Reaching for `tox`/`nox` on a single-Python-version internal service**
  where it adds real configuration overhead without a corresponding benefit
  — matching the tool to whether your project genuinely needs multi-
  environment coverage.
- **A coverage gate (`--cov-fail-under`) in the fast-checks stage**, making
  the fast feedback loop pay the cost of coverage instrumentation on every
  push when it could run once, later, in the fuller stage — a smaller
  example of the same "don't make fast feedback wait on slow work"
  principle.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/19-ci-tooling/`, write a `pyproject.toml` with a
> `[tool.pytest.ini_options]` section including `addopts = "-ra
> --strict-markers --strict-config"`, `testpaths = ["tests"]`,
> `xfail_strict = true`, registered `slow` and `integration` markers, and a
> `filterwarnings` list that turns warnings into errors except for one
> explicitly ignored, made-up noisy dependency pattern (as an example of the
> syntax). Reuse or rebuild a small `src/`+`tests/` pair from an earlier
> exercise (or a fresh trivial one) with at least 6 tests: some fast/
> unmarked, two marked `slow` (real `time.sleep`), two marked
> `integration` (using `pytest.skip` for "service unreachable" as in Lesson
> 12's exercise). Add `pytest-xdist` to `requirements-dev.txt` pinned to a
> real current version, and write a `tests/test_no_shared_state.py` file
> with two DELIBERATELY interdependent tests (test A writes to a
> module-level global list, test B asserts on that list's contents assuming
> A already ran) — have me run this file with plain `pytest` (should pass,
> misleadingly) and then with `pytest -n 2 -p no:randomly` and separately
> with `pytest -p randomly --randomly-seed=<some seed>` if `pytest-randomly`
> is easy to add (otherwise just `-n 2`) to observe it fail or become order-
> dependent — add a comment explaining what this demonstrates about hidden
> coupling, without fixing the interdependence for me. Finally, write a
> conceptual `stages` comment block (not a real CI YAML file, just
> documentation) showing how you'd split this exercise's tests into a
> fast-checks stage and a full/integration stage using `-m` expressions.

## Quiz

1. What's the practical difference between an unregistered marker producing
   a warning (default) versus an error (`--strict-markers`), in a CI
   context specifically?
2. Why is `pytest-xdist` sometimes described as a debugging tool for test
   suite design, not just a speed optimization?
3. Give a concrete reason a shared, module-level Python list used across
   tests could behave differently under `pytest-xdist -n 4` than under
   plain sequential `pytest`.
4. When is `tox`/`nox` genuinely worth the configuration overhead, and when
   is it likely overkill?
5. Why should a coverage gate (`--cov-fail-under`) typically live in a
   later/fuller CI stage rather than the fastest, first-run stage?

<details>
<summary>Answers</summary>

1. A warning can scroll past unnoticed in a long CI log, and the build
   still succeeds — meaning a typo'd marker (e.g. `@pytest.mark.slwo`)
   silently creates a useless, effectively-empty marker category and nobody
   is forced to notice or fix it. `--strict-markers` turns the same
   situation into a build failure, forcing the typo to be fixed before the
   change can merge — converting a silent, easy-to-miss correctness gap
   into a loud, immediately-actionable one.
2. Because tests that only pass due to unstated assumptions about
   sequential execution order or shared mutable state in a single process
   often fail, or behave inconsistently, once run concurrently across
   multiple separate worker processes. Running the suite under `xdist`
   surfaces this hidden coupling as a visible failure, which is valuable
   independent of whether you actually want the speedup — it's a real
   signal about test suite design quality, not just an artifact of trying
   to go faster.
3. Each `pytest-xdist` worker runs in its own separate Python process, each
   with its own independent copy of any module-level state — a list
   defined at module scope is not shared across processes the way it would
   be within a single sequential run. A test that mutates such a list and a
   later test that reads it may run in different worker processes entirely
   under `xdist`, so the second test would see the list in its own
   process's initial (unmutated) state rather than whatever the first test
   did to it, exposing the hidden dependency as a failure.
4. Worth it for libraries or tools that need to support (and verify
   correctness across) multiple Python versions or dependency version
   combinations in production — the value is directly proportional to how
   much environment variation actually matters for the project. Likely
   overkill for an internal application service deployed to one specific,
   controlled runtime version, where the added configuration and CI run
   time buys little beyond what a single pinned environment already
   verifies.
5. Because coverage instrumentation adds overhead, and computing/enforcing
   a coverage threshold isn't needed to get the primary value of fast
   feedback — knowing quickly whether the code is correct. Putting the
   coverage gate in a later, fuller pipeline stage keeps the fastest
   feedback loop (the one engineers wait on directly, on every push) as
   quick as possible, deferring the slightly slower, less time-sensitive
   check to a stage where a few extra seconds/minutes matter less.

</details>

## Further Reading

- pytest docs — [Configuration file formats](https://docs.pytest.org/en/stable/reference/customize.html)
- pytest-xdist docs — [PyPI project page and usage](https://pypi.org/project/pytest-xdist/)
- tox docs — [Basic example](https://tox.wiki/en/latest/user_guide.html)

---
Previous: [18 — Property-Based Testing with Hypothesis](18-property-based-testing-with-hypothesis.md) · Next: [20 — Flaky Tests & Anti-Patterns](20-flaky-tests-and-anti-patterns.md)
