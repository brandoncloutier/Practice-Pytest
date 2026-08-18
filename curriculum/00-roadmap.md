# Roadmap

A one-line description of every lesson. Read them in order the first pass
through — later lessons assume earlier ones.

## Phase 1 — Foundations Refresher

You already run `pytest` daily. This phase makes sure the *mental model*
underneath that habit is complete, not just the commands.

- **[01 — The pytest Mental Model](01-the-pytest-mental-model.md)**
  Test discovery, assertion rewriting, exit codes, and why plain `assert`
  works at all. The "how does this even work" lesson.
- **[02 — Fixtures 101](02-fixtures-101.md)**
  What a fixture actually is, `yield` vs `return`, the `request` object,
  and why fixtures beat `setUp`/`tearDown`.

## Phase 2 — Fixtures & Parametrization Mastery

The part of pytest that has no real equivalent in `unittest`, and the part
most self-taught pytest users under-use.

- **[03 — Fixture Scopes, Lifecycle & autouse](03-fixture-scopes-and-lifecycle.md)**
  `function`/`class`/`module`/`package`/`session`, teardown ordering, and
  the dangers (and correct uses) of `autouse=True`.
- **[04 — Fixture Composition, Factories & conftest.py](04-fixture-composition-and-conftest.md)**
  Fixtures depending on fixtures, factory-as-fixture pattern, and how
  `conftest.py` scoping actually works across a package.
- **[05 — Parametrization Mastery](05-parametrization-mastery.md)**
  `pytest.mark.parametrize` beyond the basics, stacking parametrize marks,
  `indirect=True`, parametrized fixtures, and `ids` for readable output.

## Phase 3 — Mocking Mastery

You already use `Mock`, `MagicMock`, `patch`, and `monkeypatch`. This phase
is about *knowing why they work* so you stop guessing and start choosing.

- **[06 — unittest.mock Deep Dive](06-unittest-mock-deep-dive.md)**
  `Mock` vs `MagicMock` vs `NonCallableMock`, `spec`/`spec_set`/`autospec`,
  call assertions, and side effects.
- **[07 — patch() Mechanics & Where to Patch](07-patch-mechanics-and-where-to-patch.md)**
  What `patch()` actually rewrites, the "patch where it's looked up, not
  where it's defined" rule explained mechanically, `patch.object`,
  `patch.dict`, `patch.multiple`.
- **[08 — monkeypatch vs mock.patch](08-monkeypatch-vs-mock-patch.md)**
  Overlap and differences, environment variables and `sys.path`, when each
  is the more honest tool for the job.
- **[09 — pytest-mock (the mocker fixture)](09-pytest-mock-the-mocker-fixture.md)**
  Why teams standardize on `mocker` instead of raw `unittest.mock`, spies,
  and automatic cleanup.
- **[10 — Test Doubles Strategy](10-test-doubles-strategy.md)**
  Dummy/stub/fake/spy/mock as a real taxonomy, and the discipline of
  choosing the *weakest* double that proves your point — the antidote to
  over-mocked test suites that pass against broken code.

## Phase 4 — Production Test Design

Where "tests that pass" becomes "tests you can trust and maintain."

- **[11 — Exceptions, Warnings & Logging](11-exceptions-warnings-and-logging.md)**
  `pytest.raises`, `pytest.warns`, `caplog`, and testing failure paths
  deliberately instead of by accident.
- **[12 — Markers & Test Selection](12-markers-and-test-selection.md)**
  Built-in and custom markers, `skip`/`skipif`/`xfail`, and running subsets
  of a large suite fast.
- **[13 — Test Organization at Scale](13-test-organization-at-scale.md)**
  Arrange-Act-Assert, naming conventions, one-assertion-concept-per-test,
  and test smells that show up in code review.
- **[14 — Coverage & Test Quality](14-coverage-and-test-quality.md)**
  `pytest-cov`, why 100% coverage is not the goal, and mutation testing as
  a sharper signal.

## Phase 5 — Testing Real-World Systems

- **[15 — Testing HTTP & External Services](15-testing-http-and-external-services.md)**
  `responses`/`respx`, contract stability, and not testing the internet.
- **[16 — Testing Databases & Persistence](16-testing-databases-and-persistence.md)**
  Transactional fixtures, test data factories, in-memory vs real databases.
- **[17 — Testing Async Code](17-testing-async-code.md)**
  `pytest-asyncio`, mocking coroutines, and async fixtures.
- **[18 — Property-Based Testing with Hypothesis](18-property-based-testing-with-hypothesis.md)**
  Generating test cases instead of hand-writing every example.

## Phase 6 — Team & Pipeline Practices

- **[19 — CI/CD Integration & Tooling](19-ci-cd-integration-and-tooling.md)**
  Config in `pyproject.toml`, parallelization with `pytest-xdist`, and
  running the right subset in CI.
- **[20 — Flaky Tests & Anti-Patterns](20-flaky-tests-and-anti-patterns.md)**
  Diagnosing non-determinism, and a field guide to test smells that are
  costing your team velocity right now.

## Capstone

- **[21 — Capstone Project](21-capstone-project.md)**
  Design and build a test suite for a small production-like service,
  applying every phase above and defending your design choices.
