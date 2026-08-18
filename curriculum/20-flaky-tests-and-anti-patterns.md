# Lesson 20 — Flaky Tests & Anti-Patterns

Phase 6: Team & Pipeline Practices

## Learning Objectives

- Diagnose the most common root causes of flaky (intermittently failing)
  tests: time, ordering/shared state, concurrency, and unpinned randomness.
- Apply concrete, deterministic fixes for each root cause instead of
  reflexively retrying or skipping.
- Recognize a field guide of test anti-patterns that tend to cluster
  together in a codebase, and know why each one erodes trust in the suite.
- Make the case, when needed, for why "just retry it" is a last resort, not
  a fix.

## Why This Matters in Production

A flaky test is worse than a consistently-failing one: a consistent failure
gets fixed because it blocks everyone reliably. A flaky test trains an
entire team to distrust CI red — "oh, that one's just flaky, rerun it" —
which is exactly the mental habit that lets a *real* regression slip through
disguised as "probably flaky again." This lesson exists because flaky tests
are not mysterious; nearly all of them trace back to one of a small number
of concrete, fixable root causes, and this lesson wants you leaving with the
diagnostic instinct, not just the vocabulary.

## Concept: Root Cause — Time

```python
# FLAKY
def test_session_expires_after_one_hour():
    session = create_session()
    time.sleep(1)   # "close enough" — actually just slow and still wrong
    assert not session.is_expired()

# DETERMINISTIC
def test_session_expires_after_one_hour(mocker):
    fixed_now = datetime(2026, 1, 1, 12, 0, 0)
    mocker.patch("myapp.clock.now", return_value=fixed_now)
    session = create_session()

    mocker.patch("myapp.clock.now", return_value=fixed_now + timedelta(hours=1, seconds=1))
    assert session.is_expired()
```

Any test whose correctness depends on real wall-clock time passing (sleep-
and-check patterns, "this should happen within N seconds") is a flakiness
risk under CI load variance alone — a CI runner under contention can be
slower than your `sleep()` assumed, or a network call inside that window can
take longer than expected. The fix is almost always the same: make time
itself a controllable dependency (inject a clock, or patch/monkeypatch the
function that reads the current time) instead of letting the test's
correctness depend on real elapsed wall-clock duration.

## Concept: Root Cause — Ordering and Shared State

Covered mechanically in Lessons 03 and 13 (fixture scope leakage, test
interdependence) and operationally in Lesson 19 (`pytest-xdist` as a
detector). The fix here isn't new material, it's application: run
`pytest-randomly` (a plugin that randomizes test order every run) or
`pytest-xdist` regularly, specifically to surface this class of bug before
it becomes an intermittent CI failure someone has to diagnose live, under
time pressure, without the benefit of a curriculum lesson explaining what's
happening.

## Concept: Root Cause — Concurrency and External System Timing

```python
# FLAKY — assumes an async job finishes within an arbitrary sleep window
def test_background_job_processes_message():
    enqueue_message("hello")
    time.sleep(2)
    assert get_processed_count() == 1

# DETERMINISTIC — poll with a real timeout and a clear failure message,
# or better: make the operation synchronously awaitable/observable in tests
def test_background_job_processes_message():
    enqueue_message("hello")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if get_processed_count() == 1:
            break
        time.sleep(0.05)
    else:
        pytest.fail("job did not process within 5s")
    assert get_processed_count() == 1
```

A fixed `sleep(2)` before checking an asynchronous result is a coin flip
dressed up as a test — it passes when the real system happens to be fast
enough this run, and fails when it isn't, with zero relationship to whether
the code is actually correct. A bounded poll-with-timeout is more robust
(it succeeds as soon as the condition is true, and fails clearly and
quickly if it never becomes true), but the better fix, when available, is
making the operation under test synchronously observable at all in a test
context — e.g., a test-mode queue that processes inline rather than on a
background thread — removing the race condition from the test's design
entirely rather than tolerating it with a longer timeout.

## Concept: Root Cause — Unpinned Randomness

```python
# FLAKY — occasionally fails depending on what random.choice picks
def test_shuffled_deck_deals_valid_cards():
    deck = shuffle_deck()
    hand = deal(deck, 5)
    assert len(hand) == 5   # this part's fine...
    assert hand[0] != hand[1]   # ...this part can coincidentally fail

# DETERMINISTIC — seed it
def test_shuffled_deck_deals_valid_cards():
    random.seed(42)
    deck = shuffle_deck()
    hand = deal(deck, 5)
    assert len(hand) == len(set(hand))   # assert the actual invariant, not a coincidence
```

Two separate fixes are visible here, and both matter: seeding the random
source removes run-to-run variance, and — often more importantly — the
original assertion (`hand[0] != hand[1]`) wasn't even testing the right
property; the real invariant ("no duplicate cards in a hand") should hold
regardless of which specific cards were dealt. A flaky random-input test is
often *also* a symptom of testing the wrong property — worth checking
whether Lesson 18's property-based approach (with an explicit, deliberate
seed/replay story) is actually the better tool once you notice a test
depends on "what randomness happened to produce" rather than a general
invariant.

## Concept: A Field Guide of Anti-Patterns

Quick-reference, tying together patterns from across this curriculum that
tend to cluster in troubled test suites:

| Anti-pattern | What it looks like | Where covered |
|---|---|---|
| Mystery guest | Test depends on invisible external state | Lesson 13 |
| Assertion roulette | Many unrelated assertions, unclear which failed | Lesson 13 |
| Test interdependence | Test B only passes if A ran first | Lessons 03, 13 |
| Over-specification | Asserting on incidental implementation, not behavior | Lessons 10, 13 |
| Mock-everything | Behavior-verifying internal, same-codebase collaborators | Lesson 10 |
| Sleep-and-hope | Fixed `sleep()` standing in for a real synchronization point | This lesson |
| Coverage chasing | Assertion-free tests written to move a percentage | Lesson 14 |
| Silent skip accumulation | `@pytest.mark.skip` with no reason, never revisited | Lesson 12 |
| Stale `xfail` | Non-strict `xfail` on a bug that's since been fixed | Lesson 12 |
| Retry-as-a-fix | CI configured to auto-retry flaky tests instead of fixing them | This lesson |

## Concept: Why "Just Retry It" Is a Last Resort

Automatic retry-on-failure for flaky tests (a real, available CI feature in
many setups) is sometimes a pragmatic short-term mitigation — genuinely
useful for, say, a known third-party service with occasional real
transient failures unrelated to your code. But treated as a default policy
rather than a targeted, temporary exception, it has a real cost: it
**hides the diagnostic signal** this lesson has spent its examples showing
you how to read. A test that needs three attempts to pass is telling you
something concrete — probably one of the four root causes above — and
retry logic papers over that signal instead of surfacing it. Reserve retries
for specific, understood, genuinely-external flakiness (with a comment
explaining why), and treat "let's just add a retry" as a signal to
investigate *first*, not a substitute for investigating at all.

## Common Pitfalls

- **Diagnosing flakiness as "the test environment is just unreliable"**
  without checking any of the four concrete root causes first — most
  flakiness has a specific, findable mechanism, not a vague environmental
  explanation.
- **Fixing a flaky test by increasing a `sleep()` duration.** This reduces
  the *frequency* of failure without addressing the actual race condition —
  it'll still fail eventually, likely at an inconvenient time, and the fix
  cost real time without removing the underlying bug.
- **Adding blanket CI retry logic as the first response to any red
  build**, instead of as a scoped, documented exception for a specific,
  understood external flakiness source.
- **Letting flaky tests accumulate a reputation ("oh that one's always
  flaky") instead of being fixed or quarantined explicitly** — an untracked
  flaky test is a standing erosion of trust in the whole suite's signal,
  and normalizes ignoring red builds generally.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/20-flaky-tests/`, build `src/rate_limiter.py` with a
> `RateLimiter` class that allows N calls per rolling time window, using a
> real clock dependency (inject a `clock: Callable[[], float]` defaulting
> to `time.monotonic`, so it's controllable in tests — this mirrors the
> lesson's "make time a controllable dependency" fix). Write
> `tests/test_rate_limiter_flaky.py` with a version of the tests that uses
> REAL `time.sleep()` calls and depends on real wall-clock timing to
> exercise the rolling window boundary (deliberately fragile, on purpose,
> matching this lesson's first "FLAKY" example) — add a comment predicting
> under what CI conditions this could intermittently fail even if the
> `RateLimiter` logic is correct. Then write a SEPARATE,
> `tests/test_rate_limiter_deterministic.py` using an injected fake clock
> (a simple mutable-value callable you control directly, no real sleeping)
> testing the exact same rolling-window boundary behavior deterministically
> — no `time.sleep()` anywhere in this second file. Also add
> `tests/test_shuffle_flaky_vs_property.py` with a small
> `src/cards.py` `shuffle_and_deal(deck, n)` function: first a flaky-style
> test asserting something coincidental about a specific shuffle outcome
> without seeding, then a corrected version that seeds `random` AND asserts
> the actual invariant (no duplicate cards dealt) instead. I want to be
> able to run the flaky versions repeatedly (`pytest --count=20` if
> `pytest-repeat` is easy to add, otherwise just running plain `pytest`
> several times manually) and see them occasionally behave differently,
> versus the deterministic versions which should be stable every time.

## Quiz

1. Why is a consistently-failing test, in one specific sense, "safer" for a
   team than a flaky one, even though both are undesirable?
2. A test uses `time.sleep(1)` to wait for something to happen, then
   asserts on the result. Name two different fixes with different
   tradeoffs, from most to least preferable per this lesson.
3. A random-shuffle test asserts `hand[0] != hand[1]` and occasionally
   fails. Identify two separate problems with this test, not just one.
4. Why does this lesson describe blanket CI auto-retry as something that
   "hides the diagnostic signal" rather than calling it simply wrong or
   simply right?
5. Which two tools from Lesson 19 are specifically useful for surfacing the
   "ordering and shared state" root cause of flakiness before it becomes an
   intermittent CI failure discovered live?

<details>
<summary>Answers</summary>

1. A consistently-failing test reliably blocks progress for everyone who
   encounters it, which creates strong, immediate pressure to actually fix
   it — it can't be ignored. A flaky test fails only sometimes, which
   trains the team to treat red CI as ambiguous ("maybe it's just flaky,
   rerun it") rather than as a reliable signal — that ambiguity is what
   makes flakiness more corrosive to trust in the suite over time, even
   though a permanently broken test is obviously also bad on its own terms.
2. Most preferable: remove the real-time dependency entirely by injecting a
   controllable clock or making the operation synchronously observable in
   tests (no race condition left to have timing at all). Less preferable
   but still deterministic-ish: replace the fixed sleep with a
   bounded poll-with-timeout loop that succeeds as soon as the real
   condition becomes true and fails clearly if it doesn't within a
   generous bound — better than a fixed sleep, but still tied to some real
   wall-clock behavior and thus not fully eliminating timing sensitivity.
3. First, the test isn't seeded, so its outcome depends on real
   process-level randomness and can occasionally coincidentally produce
   `hand[0] == hand[1]`... but the deeper second problem is that even a
   *correct* shuffle implementation dealing distinct cards from a deck
   could still, by chance, need `hand[0] != hand[1]` to hold for reasons
   unrelated to whether the code is correct — the assertion itself doesn't
   express the actual invariant that matters (no duplicate cards dealt),
   so fixing only the seeding without fixing the assertion would leave a
   test that passes reliably but still isn't testing the right thing.
4. Because retrying a flaky test until it passes doesn't fix anything about
   the underlying cause (one of the root causes covered in this lesson) —
   it just suppresses the visible symptom (the red build), which is exactly
   what "hiding a diagnostic signal" means: the information that something
   is wrong is still true, it's simply no longer visible to the team, which
   is a meaningfully different (and worse) outcome than either "clearly
   broken" or "genuinely fixed."
5. `pytest-randomly` (randomizes test execution order every run, directly
   surfacing order-dependence) and `pytest-xdist` (runs tests concurrently
   across separate worker processes, surfacing assumptions about shared
   in-process state that don't hold once execution is distributed) — both
   covered as detection tools for this specific root cause in Lesson 19.

</details>

## Further Reading

- pytest docs — [Flaky tests: cache, rerun, and related plugins overview](https://docs.pytest.org/en/stable/how-to/cache.html)
- pytest-randomly — [PyPI project page](https://pypi.org/project/pytest-randomly/)
- Google Testing Blog — ["Flaky Tests at Google and How We Mitigate Them"](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html) (widely cited primary source on flaky test root causes and mitigation philosophy at scale)

---
Previous: [19 — CI/CD Integration & Tooling](19-ci-cd-integration-and-tooling.md) · Next: [21 — Capstone Project](21-capstone-project.md)
