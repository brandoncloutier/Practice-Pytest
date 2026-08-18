# Lesson 11 — Exceptions, Warnings & Logging

Phase 4: Production Test Design

## Learning Objectives

- Use `pytest.raises` correctly, including `match=` and inspecting the
  captured exception via the `as` binding.
- Use `pytest.warns` to assert a warning was (or, via `pytest.warns(None)`-
  style patterns using `recwarn`, was not) raised.
- Use the `caplog` fixture to assert on log output: `caplog.text`,
  `caplog.records`, `caplog.record_tuples`, and `caplog.set_level`/
  `at_level`.
- Explain why testing failure paths deliberately (not by accident) is a
  production-quality signal, and design tests that do it.

## Why This Matters in Production

Failure paths are usually under-tested relative to how often they run in
production — retry logic, validation errors, degraded-mode fallbacks, and
deprecation warnings all tend to be written once and never exercised by
tests again, because "happy path" tests are what get written first and often
what get written *only*. This lesson is about the three built-in tools
pytest gives you specifically for testing what happens when things go wrong
or need to be logged/flagged — so "we should really test the error case" has
no remaining excuse.

## Concept: `pytest.raises`

```python
import pytest

def withdraw(balance, amount):
    if amount > balance:
        raise ValueError(f"insufficient funds: balance={balance}, amount={amount}")
    return balance - amount

def test_withdraw_raises_on_insufficient_funds():
    with pytest.raises(ValueError):
        withdraw(balance=50, amount=100)
```

`pytest.raises` is a context manager: the block **must** raise the specified
exception type (or a subclass) or the test fails with a clear
"DID NOT RAISE" message — this is meaningfully different from a bare `try`/
`except` in a test, which would silently pass if nothing raised at all
unless you added your own `pytest.fail()` in an `else` clause. Never write
that by hand; `pytest.raises` is the tool built for exactly this.

**`match=`** checks the exception's string representation against a regex:

```python
def test_withdraw_error_message():
    with pytest.raises(ValueError, match=r"insufficient funds: balance=50"):
        withdraw(balance=50, amount=100)
```

Because `match` is a regex, characters like `$`, `(`, `.` need escaping
(`re.escape(...)`) if you're matching a literal string that happens to
contain regex metacharacters — a common gotcha when message text includes
things like a dollar amount or parentheses.

**Capturing the exception object** via `as` lets you assert on more than the
message — useful for custom exception types carrying structured data:

```python
class InsufficientFundsError(Exception):
    def __init__(self, balance, amount):
        self.balance = balance
        self.amount = amount
        super().__init__(f"insufficient funds: balance={balance}, amount={amount}")

def test_withdraw_error_carries_context():
    with pytest.raises(InsufficientFundsError) as exc_info:
        withdraw(balance=50, amount=100)
    assert exc_info.value.balance == 50
    assert exc_info.value.amount == 100
```

`exc_info` is a pytest `ExceptionInfo` wrapper; `exc_info.value` is the
actual exception instance raised.

## Concept: `pytest.warns`

Same shape as `raises`, for `warnings.warn(...)` calls instead of raised
exceptions:

```python
import warnings

def load_legacy_config(path):
    warnings.warn("load_legacy_config is deprecated, use load_config",
                   DeprecationWarning)
    return {}

def test_legacy_config_warns():
    with pytest.warns(DeprecationWarning, match="load_legacy_config is deprecated"):
        load_legacy_config("old.cfg")
```

Note pytest's default behavior here matters operationally: pytest surfaces
`DeprecationWarning` and `PendingDeprecationWarning` from your own code and
third-party libraries by default (following Python's own recommendation in
PEP 565), which is why you'll often see deprecation warnings show up in a
test summary even for tests that don't explicitly check for them — a useful
early-warning system for "a dependency you use is about to break" that's
easy to miss if you only skim for red failures and ignore yellow warnings
sections.

## Concept: `caplog`

`caplog` captures log records emitted during a test, without you needing to
configure handlers manually:

```python
import logging

def process_payment(amount):
    logger = logging.getLogger("payments")
    if amount <= 0:
        logger.warning("Rejected non-positive payment amount: %s", amount)
        return False
    logger.info("Processed payment of %s", amount)
    return True

def test_rejects_and_logs_non_positive_amount(caplog):
    with caplog.at_level(logging.WARNING):
        result = process_payment(-5)
    assert result is False
    assert "Rejected non-positive payment amount: -5" in caplog.text

def test_logs_structured_record(caplog):
    caplog.set_level(logging.INFO)
    process_payment(100)
    assert caplog.record_tuples == [
        ("payments", logging.INFO, "Processed payment of 100"),
    ]
```

- **`caplog.text`** — the full captured log output as one string; good for
  simple substring assertions.
- **`caplog.records`** — the actual `logging.LogRecord` objects, letting you
  check `.levelname`, `.name` (logger name), or other structured fields
  precisely instead of substring-matching text.
- **`caplog.record_tuples`** — a convenience list of
  `(logger_name, level, message)` tuples, often the cleanest single
  assertion for "exactly these log lines happened."
- **`caplog.set_level(level, logger=None)`** — sets the capture level for
  the rest of the test (or a specific named logger).
- **`caplog.at_level(level, logger=None)`** — a context manager scoping the
  level change to just its `with` block, then restoring it — same idea as
  `monkeypatch.context()` from Lesson 08, applied to logging.

## Common Pitfalls

- **Wrapping too much code inside `pytest.raises`.** If a 10-line block is
  inside the `with pytest.raises(...):` context and the exception actually
  gets raised on line 2 instead of the line you intended, the test still
  passes — but it isn't testing what you think. Keep the block as narrow as
  possible, ideally just the single call expected to raise.
- **Not using `match=` and later having the exception's message text change
  in a way that breaks correctness but not the test.** A bare
  `pytest.raises(ValueError)` with no `match` will pass even if the actual
  error message is now nonsensical — matching the message (at least a
  meaningful substring) closes that gap when the message content matters to
  correctness (e.g., it's user-facing or logged for on-call debugging).
- **Forgetting the default log level.** If a test asserts on `caplog.text`
  but the emitting code logs at `DEBUG` and the effective level is `WARNING`,
  the record is never captured and the assertion fails confusingly. Set the
  level explicitly with `caplog.set_level`/`at_level` rather than assuming.
- **Testing that a warning was raised, but not that the *code still behaves
  correctly* afterward.** A deprecation warning test that doesn't also
  assert the deprecated function still returns the right value is only
  half the test — the function needs to keep working during its deprecation
  period, not just announce that it's deprecated.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/11-exceptions-warnings-logging/`, create
> `src/account.py` with an `Account` class with a `withdraw(amount)` method
> that: raises a custom `InsufficientFundsError(balance, amount)` (carrying
> both values as attributes) if `amount > balance`; raises `ValueError` if
> `amount <= 0`; logs a `logging.getLogger("account")` warning any time a
> withdrawal is rejected for either reason, with the reason distinguishable
> in the message; and emits a `DeprecationWarning` if a soon-to-be-removed
> keyword argument `legacy_mode=True` is passed. Then write
> `tests/test_account.py` covering: (1) `pytest.raises` with `match=` for
> the `ValueError` case; (2) `pytest.raises(...) as exc_info` for the
> `InsufficientFundsError` case, asserting on `exc_info.value.balance` and
> `.amount` directly, not just the message string; (3) a `caplog` test
> using `record_tuples` to assert the exact logger name, level, and message
> for a rejected withdrawal; (4) a `pytest.warns` test for the
> `legacy_mode=True` deprecation path, which ALSO asserts the withdrawal
> still completes correctly despite the warning (both behaviors checked in
> one test, on purpose, per the lesson's "test failure paths and correct
> behavior together" point). Include one deliberately too-broad
> `pytest.raises` block (wrapping several lines instead of one call) with a
> comment asking me to identify why it's a weaker test than the narrow
> version, without fixing it for me.

## Quiz

1. Why is `pytest.raises(SomeError)` structurally safer as a test idiom
   than a manual `try: ... except SomeError: pass else: pytest.fail(...)`?
2. What's the risk of putting more than the single line you expect to raise
   inside a `pytest.raises(...)` block?
3. Given `pytest.raises(ValueError, match=r"amount=100")`, why might this
   fail to match even if the real error message clearly contains
   "amount=100" as a substring — what's the fix?
4. What does `caplog.at_level(logging.DEBUG)` do differently from
   `caplog.set_level(logging.DEBUG)` in terms of scope/duration?
5. Why does this lesson recommend asserting both "the warning was raised"
   and "the function still behaved correctly" in the same test, for
   deprecation-warning scenarios specifically?

<details>
<summary>Answers</summary>

1. `pytest.raises` fails the test explicitly and clearly ("DID NOT RAISE")
   if the expected exception never occurs inside the block. A hand-rolled
   `try/except/else` requires the author to remember to add the `else:
   pytest.fail(...)` branch — forgetting it means the test silently passes
   whether or not the exception was actually raised, which defeats the
   purpose of the test entirely and is easy to miss in review.
2. If the block contains multiple statements, the exception could be raised
   by an earlier line than the one you actually meant to test, and the test
   would still pass — but it's no longer testing what you believe it's
   testing. A narrow block (ideally just the one call) ties the assertion
   to the specific operation you intend to verify.
3. Because `match` treats its argument as a **regex pattern**, and `(` in
   `"amount=100"` isn't present here so that's fine — but characters like
   `$`, `.`, `(`, `)`, `[`, `]` in the target string would need
   `re.escape()` if present, since they have special regex meaning.  (If the
   actual message text contains such characters near "amount=100" and they
   aren't escaped, the pattern may fail to match even though the substring
   is visually present.) The general fix is wrapping literal text you want
   matched exactly with `re.escape()` before passing it to `match=`.
4. `caplog.at_level(...)` is a context manager — the level change applies
   only within its `with` block and is automatically restored to whatever
   it was before once the block exits. `caplog.set_level(...)` changes the
   level for the rest of the test (no automatic scoping/restoration within
   the test itself) unless you call it again.
5. Because a deprecation warning is supposed to signal "this still works,
   but please migrate" — if a test only checks that the warning fires and
   never checks the function's actual return value/behavior, a regression
   that broke the deprecated path entirely (while still correctly emitting
   the warning) would pass that test undetected. Checking both together
   verifies the code is honoring the deprecation contract: still functional,
   properly flagged.

</details>

## Further Reading

- pytest docs — [Asserting expected exceptions with `pytest.raises`](https://docs.pytest.org/en/stable/how-to/assert.html#assertions-about-expected-exceptions)
- pytest docs — [Asserting warnings with `pytest.warns`](https://docs.pytest.org/en/stable/how-to/capture-warnings.html)
- pytest docs — [How to manage logging (`caplog`)](https://docs.pytest.org/en/stable/how-to/logging.html)

---
Previous: [10 — Test Doubles Strategy](10-test-doubles-strategy.md) · Next: [12 — Markers & Test Selection](12-markers-and-test-selection.md)
