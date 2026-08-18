# Lesson 10 — Test Doubles Strategy

Phase 3: Mocking Mastery

## Learning Objectives

- Name and distinguish the five classic test double categories: dummy,
  stub, fake, spy, mock (in the strict, original sense of that term).
- Explain why "mock everything" produces suites that pass against broken
  code, with a concrete example.
- Apply a decision process for choosing the weakest double that still lets
  a test prove what it needs to prove.
- Identify over-mocked tests in review and articulate what's wrong with
  them specifically.

## Why This Matters in Production

This is arguably the most important lesson in Phase 3, and the one most
engineers skip because "mock" has become the generic verb for "replace a
dependency in a test," collapsing five genuinely different tools into one
word and one instinct. The result, at scale, is test suites full of tests
that assert a mock was called the way the test author *assumed* the code
would call it — which is circular if the code changes to call it differently
in a way that's still correct, or worse, stays green if the code calls it in
a way that's subtly *wrong* but happens to match the mock's configured
behavior. Knowing the taxonomy is how you catch yourself reaching for a
mock when a fake, or no double at all, would produce a more trustworthy
test.

## Concept: The Taxonomy

This taxonomy originates from Gerard Meszaros's "xUnit Test Patterns" and
was popularized further by Martin Fowler's writing on the subject — it
predates and is broader than any specific Python library. In Python, you'll
typically *build* several of these using `unittest.mock` classes, but the
category is about **what role the double plays in the test**, not which
class you instantiate.

**Dummy** — an object passed in only to satisfy a parameter list; never
actually used by the code path under test.

```python
def test_calculate_shipping_cost():
    dummy_logger = object()   # required param, never called in this path
    cost = calculate_shipping_cost(weight=5, logger=dummy_logger)
    assert cost == 12.50
```

**Stub** — provides canned answers to calls made during the test; no
verification of *how* it was called, just supplies input the code under
test needs to proceed.

```python
def test_discount_applied_for_premium_user(mocker):
    stub_user_service = mocker.Mock()
    stub_user_service.get_tier.return_value = "premium"
    price = calculate_price(base=100, user_service=stub_user_service)
    assert price == 90   # we only care about the OUTPUT, not the stub's calls
```

**Fake** — a working, simplified implementation, not just canned answers —
genuinely has behavior (an in-memory dict standing in for a database is the
classic example), just not production-grade (no persistence, no real
network, no real scaling concerns).

```python
class FakeUserRepository:
    def __init__(self):
        self._users = {}
    def save(self, user):
        self._users[user.id] = user
    def get(self, user_id):
        return self._users.get(user_id)

def test_registration_persists_user():
    repo = FakeUserRepository()
    register_user(repo, name="Ada")
    assert repo.get(1).name == "Ada"   # real behavior, not a canned answer
```

**Spy** — records how it was called (arguments, call count) while typically
also either forwarding to a real implementation or acting as a stub — used
when the *fact of the call*, not just an output value, is what the test
needs to verify. Covered concretely with `mocker.spy` in Lesson 09.

**Mock** (strict sense) — pre-programmed with expectations about the calls
it will receive, and used to verify those expectations were met — behavior
verification, not state verification. `unittest.mock.Mock` with
`assert_called_with(...)` is exactly this.

## Concept: Why "Mock Everything" Produces Untrustworthy Suites

Here's the failure mode concretely. Suppose the real behavior:

```python
def apply_discount(user_service, base_price, user_id):
    tier = user_service.get_tier(user_id)
    if tier == "premium":
        return base_price * 0.9
    return base_price
```

An over-mocked test:

```python
def test_apply_discount(mocker):
    mock_service = mocker.Mock()
    mock_service.get_tier.return_value = "premium"
    result = apply_discount(mock_service, 100, user_id=42)
    mock_service.get_tier.assert_called_once_with(42)
    assert result == 90
```

This looks fine in isolation — and it *is* fine, because `get_tier` is an
external collaborator (say, a network call to a user service) that
legitimately shouldn't run in a fast unit test. The taxonomy's real lesson
shows up when this pattern is applied to something that **isn't** an
external boundary:

```python
def apply_discount(pricing_engine, base_price, user_id):
    return pricing_engine.compute(base_price, user_id)

def test_apply_discount_over_mocked(mocker):
    mock_engine = mocker.Mock()
    mock_engine.compute.return_value = 90
    result = apply_discount(mock_engine, 100, user_id=42)
    assert result == 90   # trivially true: the mock was TOLD to return 90
```

This test provides almost zero value: it proves `apply_discount` calls
`.compute(...)` and returns whatever it got back — which is nearly
tautological, not a meaningful check of actual discount logic. If
`pricing_engine.compute` is really *internal* logic you own (not a genuine
external system, not slow, not non-deterministic), the correct double is
**no double at all** — use the real `PricingEngine`, or at most a **fake**
with simplified-but-real behavior, and assert on real computed output. The
mock in this version tests that a wire is connected, not that electricity
flows correctly through it.

## Concept: A Decision Process

When you're about to introduce a test double, ask in order:

1. **Is this a real boundary** — network, filesystem, wall-clock time,
   randomness, a slow/expensive external system, or something with real
   side effects you don't want in a test run? If **no**, don't double it at
   all; use the real thing.
2. **If yes: does the test care about the *value* the collaborator returns**,
   and not about how it was called? → **stub**.
3. **Does the test need genuinely correct-but-simplified behavior across
   several calls** (e.g., save-then-retrieve consistency)? → **fake**.
4. **Does the test specifically need to verify a call happened, with what
   arguments, while the real logic still needs to run** (e.g., "did we log
   this," "did we enqueue this job") → **spy**.
5. **Does the test need to verify an *interaction* with a collaborator was
   correct — call count, argument shape, ordering — and the collaborator's
   own return value doesn't matter much beyond making the test runnable**?
   → **mock** (behavior verification).
6. **Is the double just there to satisfy a required parameter that this
   code path never touches?** → **dummy**.

The discipline this process enforces: **choose the weakest double that
still lets the test prove what it's actually supposed to prove.** A mock
(behavior verification) is the strongest, most coupling-prone tool in this
list — it ties your test to *how* the code calls its collaborator, not just
*what* it produces — and should be reserved for when that coupling is
genuinely what you want to verify (e.g., "we must call `send_webhook`
exactly once per event, even though we don't control what it returns").

## Common Pitfalls

- **Mocking internal, same-codebase collaborators as a reflex.** If both
  sides of the mock boundary are code you own, deployed together, and fast
  to run for real, a mock usually buys you nothing but coupling to
  implementation details.
- **Writing behavior-verification tests (mock, asserting call args) for
  things that only need state-verification (stub/fake, asserting on
  output).** This makes tests brittle to legitimate refactors — the
  behavior didn't change, but the *shape* of an internal call did, and the
  test breaks anyway.
- **A fake that's drifted from the real implementation's contract.** If your
  `FakeUserRepository` allows saving a user with a duplicate ID but the real
  database enforces a unique constraint, tests against the fake give false
  confidence. Fakes need occasional contract tests (Lesson 16 touches this)
  to keep them honest.
- **Treating "I used `Mock()`" as inherently meaning "this is a mock" in the
  strict sense.** `unittest.mock.Mock` is a *class* you can configure to
  behave as a dummy, stub, spy, or mock depending on how you use it in a
  given test — the taxonomy is about role, not which import statement you
  used.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/10-test-doubles/`, build a small `src/order_service.py`
> with an `OrderService` class that depends on three collaborators injected
> via its constructor: a `PaymentGateway` (a genuine external boundary — has
> a `charge(amount)` method), an `OrderCalculator` (pure internal logic —
> has a `total(items: list[float], tax_rate: float) -> float` method with
> real, non-trivial rounding behavior), and a `Notifier` (an external
> boundary — has a `notify(message: str)` method). `OrderService.place_order
> (items, tax_rate)` should compute the total via `OrderCalculator`, charge
> it via `PaymentGateway`, and notify via `Notifier`, returning a summary
> dict. In `tests/test_order_service.py`, write five tests, one per double
> type, each with a comment naming which double category it is and *why*
> that's the right choice for that specific collaborator: (1) a **dummy**
> test where `Notifier` is passed as a dummy because a specific code path
> (e.g., a zero-item order that raises before notifying) never calls it;
> (2) a **stub** test where `PaymentGateway.charge` returns a canned
> transaction ID and the test only checks the returned summary dict's
> content; (3) a **fake** test using a real (but simplified/in-memory)
> `OrderCalculator` — NOT mocked — proving the actual tax/rounding math,
> since that's internal logic worth testing for real; (4) a **spy** test
> wrapping the real `Notifier.notify` (via `mocker.spy`) to prove the exact
> message content sent, while still letting it "really" run against a fake
> in-memory notification list; (5) a **mock** (behavior-verification) test
> asserting `PaymentGateway.charge` was called exactly once with the
> correct computed amount — the one test in this set where interaction
> verification is the actual point, because "we must charge exactly once"
> is a real business requirement. Deliberately do NOT mock
> `OrderCalculator` anywhere — leave a comment explaining why that would
> have been the "mock everything" anti-pattern from the lesson.

## Quiz

1. In the strict taxonomy, what's the difference between a stub and a mock?
2. Give an original example (not from this lesson) of an internal,
   same-codebase collaborator that's usually a mistake to mock, and explain
   what a test loses by mocking it anyway.
3. Why is a spy sometimes the more honest choice than a mock when you want
   to verify a logging call happened?
4. What's the risk of a fake drifting from the real implementation's actual
   contract, and what mitigates it (name-drop the concept even if the full
   technique is covered later)?
5. Walk through the six-step decision process from this lesson for a
   collaborator that reads a feature flag from a fast, in-process
   configuration object your own team owns and ships in the same deploy.

<details>
<summary>Answers</summary>

1. A stub supplies canned return values so the code under test can proceed,
   and the test verifies *output/state* — it typically doesn't matter (or
   isn't asserted) exactly how the stub was called. A mock, in the strict
   sense, is pre-programmed with expectations about calls and is used
   specifically to verify *that the interaction happened correctly*
   (arguments, call count) — behavior verification rather than state
   verification, even if the mock's return value is barely relevant to the
   test.
2. Example: a `TaxCalculator` used internally by an `OrderService`, both in
   the same codebase, deployed together, with no I/O. Mocking it means the
   test only proves `OrderService` calls `.calculate(...)` and uses the
   return value — it proves nothing about whether the tax math is actually
   correct, and remains green even if `TaxCalculator`'s real logic is
   broken, since the mock's canned return value was hardcoded by the test
   author, not computed by real code.
3. Because a spy still lets the real logging call execute — so the test
   proves the actual log message content and that real logging
   infrastructure works, not just that some object's `.info()` attribute
   was invoked. A mock replacing the logger entirely would prevent real
   logging from running at all during the test, which is fine if the goal
   is purely "was it called," but loses the ability to verify real
   behavior alongside the call itself.
4. The risk is false confidence: tests pass against the fake's behavior,
   but the fake no longer matches what the real system actually does (e.g.,
   a fake in-memory repository that allows duplicate IDs when the real
   database enforces uniqueness), so a bug that the real system would catch
   slips through. This is mitigated by periodically running the same
   behavioral contract/test suite against both the fake and the real
   implementation — a technique often called a "contract test," touched on
   again in Lesson 16.
5. Step 1: is this a real boundary (network, filesystem, wall-clock,
   randomness, slow/external system)? No — it's fast, in-process, and owned
   by the same team/deploy. That answer alone means the process stops at
   step 1: don't double it at all — use the real configuration object in
   the test. Doubling it would only be justified if, for example, you
   specifically needed to test behavior under a flag value that's difficult
   to construct through the real object's normal API.

</details>

## Further Reading

- Martin Fowler — [Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html) (the canonical explanation of this taxonomy and the state-vs-behavior verification distinction)
- Python docs — [`unittest.mock` — `Mock(wraps=...)`, the building block for spies](https://docs.python.org/3/library/unittest.mock.html#calling)

---
Previous: [09 — pytest-mock (the mocker fixture)](09-pytest-mock-the-mocker-fixture.md) · Next: [11 — Exceptions, Warnings & Logging](11-exceptions-warnings-and-logging.md)
