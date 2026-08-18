# Lesson 13 — Test Organization at Scale

Phase 4: Production Test Design

## Learning Objectives

- Apply the Arrange-Act-Assert structure consistently, and recognize when a
  test violates it.
- Write test names that describe behavior, not implementation.
- Identify and name common "test smells": mystery guest, assertion roulette,
  test interdependence, and over-specification.
- Decide where a given test belongs (unit vs. integration directory) using
  a concrete criterion, not a vibe.

## Why This Matters in Production

A test suite with 3,000 tests that nobody wants to touch — because nobody's
confident what would actually break if they changed something, or because a
failing test's name gives no hint what went wrong — is a liability that
looks like an asset on a coverage dashboard. This lesson is about the
readability and structural conventions that keep a large suite navigable
years into a project, written by people who've long since moved to other
teams.

## Concept: Arrange-Act-Assert (AAA)

Every good unit test has (at most) three phases, and keeping them visually
separated is worth the discipline:

```python
def test_discount_applied_for_premium_customer():
    # Arrange
    customer = Customer(tier="premium")
    cart = Cart(items=[Item(price=100)])

    # Act
    total = calculate_total(cart, customer)

    # Assert
    assert total == 90
```

This mirrors "Given/When/Then" from behavior-driven-development phrasing —
same structure, different vocabulary. The value isn't the comments (skip
them once the habit is automatic); it's that a reader can immediately locate
*what's being set up*, *what's being exercised*, and *what's being checked*,
without re-reading the whole function to figure out which lines matter.

A test that interleaves setup, action, and assertion throughout its body —
asserting mid-way through, then doing more setup, then acting again — is
harder to debug when it fails, because it's unclear which "phase" the
failure actually belongs to.

## Concept: Naming Tests for Behavior, Not Implementation

Compare:

```python
def test_calculate_total():             # what about it?
    ...

def test_calculate_total_case_2():      # even less informative
    ...

def test_calculate_total_applies_discount_for_premium_customers():  # clear
    ...
```

A good test name should let someone reading a CI failure list understand
*what broke*, in business terms, without opening the file. This especially
matters at scale: a CI failure notification showing
`test_calculate_total_applies_discount_for_premium_customers FAILED` is
immediately actionable; `test_calculate_total_case_2 FAILED` sends the
reader straight into the source before they even know if this is their
problem to fix.

A related, common naming convention worth adopting deliberately:
`test_<unit_under_test>_<condition>_<expected_outcome>` — e.g.
`test_withdraw_amount_exceeds_balance_raises_insufficient_funds`. It reads
almost like a sentence, and it front-loads the condition and outcome, which
is exactly the information a failure list needs first.

## Concept: Test Smells

**Mystery guest** — a test depends on external state (a file, a database
row, an environment variable) that isn't visible anywhere in the test itself
— the reader has to go hunting for where that state came from.

```python
# BAD — where does user id 42 come from? What data does it have?
def test_get_user_profile():
    profile = get_user_profile(42)
    assert profile.name == "Ada Lovelace"

# BETTER — the "guest" is now visible in the test itself
def test_get_user_profile(make_user):
    user = make_user(name="Ada Lovelace")
    profile = get_user_profile(user.id)
    assert profile.name == "Ada Lovelace"
```

**Assertion roulette** — many assertions in one test with no way to tell,
from the failure output alone, which one actually failed (worse without
messages, but even with messages, too many unrelated checks crammed into one
test obscure which concept broke).

```python
# BAD — if this fails, which of the four things is actually wrong?
def test_user_registration():
    user = register("ada@example.com", "Ada")
    assert user.email == "ada@example.com"
    assert user.name == "Ada"
    assert user.is_active is True
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Welcome!"
```

This isn't "never have more than one assertion" (a common oversimplification
of this principle) — multiple assertions about *one concept* are fine and
often necessary (e.g., checking several fields of the same returned object).
The smell is multiple assertions about **unrelated concepts** crammed into
one test, where a failure doesn't tell you *which* concept broke without
reading the traceback carefully. The fix above is usually to split by
concept: one test for the user's own fields, a separate test for the welcome
email being sent — each with a name that tells you exactly what failed.

**Test interdependence** — test B only passes if test A ran first (shared
mutable state, execution-order assumptions). This is Lesson 03's
session-scope leakage risk showing up as a design smell rather than a bug:
if your suite can't be safely run with `pytest-randomly` or a subset
selected via `-k`, you likely have this problem.

**Over-specification** — asserting on incidental implementation details a
behavior change shouldn't have to care about (exact call counts to internal
helper functions, exact private attribute names) rather than on observable
behavior. This is Lesson 10's "mock everything" problem viewed as a broader
organizational smell: tests that are brittle to legitimate refactors because
they encode *how* something happens instead of *what* happens.

## Concept: Where Does This Test Belong?

A workable, concrete criterion instead of a vibe-based one:

- **Unit test**: exercises one unit of behavior in-process, with all real
  external boundaries (Lesson 10's taxonomy) replaced by doubles. Should run
  in milliseconds and require no network, no real database, no filesystem
  beyond `tmp_path`.
- **Integration test**: exercises real interaction between your code and a
  real (or realistically faked, e.g. a test container) external system —
  a real database, a real HTTP call to a service you control, real
  serialization across a process boundary.
- **End-to-end test**: exercises the whole deployed system (or a close
  approximation) the way a user or external client actually would.

Put the test in the directory matching which of these it is — `tests/unit/`,
`tests/integration/`, `tests/e2e/` — and mark it accordingly (Lesson 12).
The criterion to apply when you're unsure: **"if I deleted every external
system this test touches and replaced it with a broken stub, would this
test still be correct to write and run?"** If yes, it's testing your own
logic and belongs in `unit/`. If the whole point is proving the real
interaction works, it belongs in `integration/` (or `e2e/`).

## Common Pitfalls

- **A giant "test everything about this feature" test function.** Split by
  concept — smaller, well-named tests are more useful failure signals than
  one large test that happens to also run faster to write.
- **Copy-pasting a passing test and tweaking one line for a new case,
  repeatedly, instead of parametrizing (Lesson 05) or extracting shared
  setup (Lesson 04).** This is how suites end up with dozens of
  near-identical tests that drift subtly out of sync over time.
- **Naming tests after the function under test alone
  (`test_calculate_total`) with numbered variants.** Doesn't scale past
  2–3 cases before the numbers become meaningless.
- **Treating "more assertions per test" as more thorough**, when it's often
  the opposite — a wall of unrelated assertions makes failures harder to
  interpret, not easier.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/13-test-organization/`, take an intentionally poorly
> organized existing test file — write `tests/test_messy_original.py` with
> a `src/inbox.py` module (an `Inbox` class: `add_message(sender, subject,
> body)`, `mark_read(message_id)`, `unread_count()`) and ONE giant test
> function that does five unrelated things (adds three messages, checks
> unread count, marks one read, checks unread count again, checks a message
> field, and asserts on an internal private list's length directly) with
> vague variable names and no AAA structure, riddled with the "assertion
> roulette" and "over-specification" smells from this lesson. Then, in a
> separate `tests/test_inbox.py`, refactor it into properly separated,
> well-named, AAA-structured tests — but leave that second file for ME to
> write, with only a docstring listing the distinct behaviors to split it
> into (don't write the refactored version yourself). I want to practice
> the refactor by hand and then compare notes. Once I've done it, I'll ask
> you for a review.

## Quiz

1. What's the difference between "multiple assertions in one test" being
   fine versus being an "assertion roulette" smell?
2. A test named `test_process_order_2` fails in CI. What's wrong with this
   from a triage-speed perspective, independent of whether the test itself
   is correct?
3. Define "mystery guest" in your own words and describe the fix pattern
   shown in this lesson.
4. Give the concrete criterion this lesson proposes for deciding whether a
   test belongs in `unit/` versus `integration/`.
5. Why is test interdependence (test B only passing if test A ran first)
   dangerous specifically in a codebase that also uses `pytest-xdist` or
   `pytest-randomly`?

<details>
<summary>Answers</summary>

1. Multiple assertions about the *same concept* (e.g., several fields of one
   returned object) are fine — they're really one logical check expressed
   across several lines. "Assertion roulette" is multiple assertions about
   *unrelated concepts* in one test, where a failure doesn't tell you, from
   the output alone, which of several unrelated things actually broke —
   forcing a reader to dig through the traceback and the test body together
   just to understand what failed.
2. The name gives no information about what behavior is being tested or
   what "2" distinguishes it from case "1" — a reader triaging a CI failure
   list has to open the source file just to understand the failure's
   subject matter, which is exactly the information a good test name should
   surface immediately without that extra step.
3. A "mystery guest" is external state the test depends on that isn't
   visible anywhere in the test itself — e.g., a hardcoded user ID whose
   underlying data lives somewhere the reader can't see from the test. The
   fix is to construct that state visibly inside the test (often via a
   factory fixture, per Lesson 04) so everything the test depends on is
   readable in the test itself, not hidden in a database seed script or
   another file.
4. Ask: "if every external system this test touches were replaced with a
   broken stub, would this test still be correct to write and run?" If yes
   — the test is really about your own logic, independent of any real
   external system — it belongs in `unit/`. If the whole point of the test
   is proving a real interaction with an external system actually works, it
   belongs in `integration/` (or `e2e/` for a full deployed-system check).
5. Both tools intentionally change execution order (`pytest-randomly`) or
   run tests in parallel across separate worker processes
   (`pytest-xdist`), which breaks any assumption that test A's side effects
   are still present (or even that A ran in the same process at all) by the
   time test B runs. A suite with interdependent tests will pass under
   plain sequential `pytest` but fail unpredictably under either of these
   tools — often the first real signal a team gets that hidden
   interdependence existed at all.

</details>

## Further Reading

- Martin Fowler — [GivenWhenThen](https://martinfowler.com/bliki/GivenWhenThen.html)
- pytest docs — [Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- xUnit Test Patterns (Gerard Meszaros) — the original catalog of test
  smells referenced throughout this lesson; summarized widely, but the book
  is the primary source if you want the full taxonomy.

---
Previous: [12 — Markers & Test Selection](12-markers-and-test-selection.md) · Next: [14 — Coverage & Test Quality](14-coverage-and-test-quality.md)
