# Lesson 06 — unittest.mock Deep Dive

Phase 3: Mocking Mastery

## Learning Objectives

- Explain the difference between `Mock`, `MagicMock`, and `NonCallableMock`,
  and pick the right one deliberately.
- Use `spec`, `spec_set`, and `autospec`/`create_autospec` to make mocks fail
  loudly when misused, instead of silently accepting anything.
  the difference between `return_value` and `side_effect`, including
  `side_effect` as a function, an exception, and an iterable.
- Explain why plain `Mock()` can let a misspelled assertion (like
  `mock.asert_called_once_with(...)`) pass silently, and how spec-based
  mocks prevent it.

## Why This Matters in Production

You already use `Mock`, `MagicMock`, `patch`, and `parametrize` daily. What
usually separates "I use mocks" from "I trust my mocked tests" is `spec`.
An un-spec'd mock will happily let your test call a method that doesn't
exist on the real object, pass arguments the real method doesn't accept, or
tolerate a typo'd assertion — and still report green. That's a test that
protects you from nothing. This lesson is specifically about closing that
gap.

## Concept: Mock, MagicMock, NonCallableMock

```python
from unittest.mock import Mock, MagicMock, NonCallableMock

m = Mock()
m()                      # fine — Mock is callable by default, returns a Mock
m.anything.goes.here()   # fine — attributes are created on access, recursively

mm = MagicMock()
str(mm)                  # fine — MagicMock preconfigures dunder/"magic" methods
len(mm)                  # fine — __len__ is preconfigured too (defaults to 0)
for _ in mm: ...         # fine — __iter__ is preconfigured

nc = NonCallableMock()
nc()                     # raises TypeError — this object isn't supposed to be callable
```

**`Mock`** is the base: attribute access auto-vivifies more mocks, and calling
it returns a `Mock` by default. It does **not** implement Python's "magic
methods" (`__len__`, `__iter__`, `__enter__`, etc.) — if your production code
does `len(obj)` or uses `obj` as a context manager, a plain `Mock` in that
slot raises `TypeError`, because those special methods are looked up on the
*type*, not the instance, and plain `Mock` doesn't define them.

**`MagicMock`** is a `Mock` subclass with the common magic methods
preconfigured. Use it whenever the object you're replacing is used in ways
that rely on Python protocols — iterated over, used as a context manager,
compared, indexed, etc. `patch()` and `mocker.patch()` (Lessons 07/09) both
default to producing a `MagicMock`, precisely because "does this object get
used like `obj[...]` or `with obj:` anywhere" is common enough to be the safe
default.

**`NonCallableMock`** (and `NonCallableMagicMock`) exist for the — less
common but real — case where you're mocking something that genuinely isn't
supposed to be called, like a module or a plain data object, and you want a
test to fail loudly if your code under test accidentally tries to call it.

## Concept: `spec`, `spec_set`, `autospec`

By default, a `Mock`/`MagicMock` accepts *any* attribute access or method
call — there's no relationship to a real class or object, so there's nothing
to check against. `spec` fixes that:

```python
class PaymentGateway:
    def charge(self, amount: float, currency: str) -> str:
        ...

mock_gateway = Mock(spec=PaymentGateway)
mock_gateway.charge(10.0, "USD")   # fine — charge exists on PaymentGateway
mock_gateway.refund(10.0)          # raises AttributeError — refund doesn't exist
```

`spec` restricts what attributes/methods can be *accessed* on the mock to
what exists on the real class. `spec_set` goes further and also restricts
*setting* new attributes:

```python
mock_gateway = Mock(spec_set=PaymentGateway)
mock_gateway.new_field = "oops"    # raises AttributeError — not on PaymentGateway
```

Neither `spec` nor `spec_set` checks **call signatures** — `mock_gateway.
charge()` with zero arguments, or `charge(amount="wrong-type")`, will still
succeed, because `spec` only checks attribute *existence*, not how callables
are invoked. That's what `autospec` is for:

```python
from unittest.mock import create_autospec

mock_gateway = create_autospec(PaymentGateway, instance=True)
mock_gateway.charge(10.0)          # raises TypeError — missing 'currency'
mock_gateway.charge(10.0, "USD")   # fine
```

`autospec` (via `create_autospec`, or `patch(..., autospec=True)`) inspects
the real object's signature and enforces it, recursively, on every attribute
it exposes. It's strictly stronger than `spec`, and strictly more expensive
to construct — for most production test suites, defaulting to `autospec`
wherever you're patching a real collaborator is the right tradeoff, reserving
plain `Mock()`/`MagicMock()` for cases where you're not modeling a real
object at all (e.g., a throwaway callback).

## Concept: `return_value` vs `side_effect`

```python
mock_fn = Mock(return_value=42)
mock_fn()          # 42, every time, regardless of arguments

mock_fn = Mock(side_effect=[1, 2, 3])
mock_fn(), mock_fn(), mock_fn()     # 1, 2, 3 — then StopIteration on a 4th call

mock_fn = Mock(side_effect=ConnectionError("timeout"))
mock_fn()          # raises ConnectionError("timeout")

def custom_behavior(x):
    if x < 0:
        raise ValueError("negative")
    return x * 2

mock_fn = Mock(side_effect=custom_behavior)
mock_fn(5)          # 10 — side_effect function's return value is used
mock_fn(-1)         # raises ValueError
```

`return_value` is a static answer. `side_effect` is dynamic behavior: a
callable (invoked with the same args, its return value used unless it
returns the sentinel `mock.DEFAULT`), an exception (raised), or an iterable
(consumed one value per call). Use `side_effect` whenever the test cares
about *behavior over multiple calls* or needs to simulate a failure —
`return_value` alone can't raise an exception or vary across calls.

## Concept: Call Assertions, and the Footgun `spec` Prevents

```python
mock_fn.assert_called()                    # called at least once
mock_fn.assert_called_once()               # called exactly once
mock_fn.assert_called_with(10, "USD")      # most recent call matched these args
mock_fn.assert_called_once_with(10, "USD") # called exactly once, with these args
mock_fn.assert_any_call(10, "USD")         # matched these args on ANY call
mock_fn.assert_not_called()
```

Here's the historical footgun this lesson exists partly to warn you about:
on a plain, un-spec'd `Mock`, **any** attribute access — including a
misspelled assertion method — creates a new child mock rather than raising
an error:

```python
mock_fn = Mock()
mock_fn(10, "USD")
mock_fn.asert_called_once_with(10, "USD")   # typo: "asert", not "assert"
# On old mock versions this silently created a new Mock attribute and
# did nothing — the "assertion" never happened, and the test passed
# regardless of what mock_fn was actually called with.
```

Modern `unittest.mock` (Python 3.8+) mitigates this directly: by default,
attribute access for names starting with `assert`, `assret`, `asert`,
`aseert`, or `assrt` on a `Mock`/`MagicMock` raises `AttributeError` unless
you explicitly pass `unsafe=True`. That default catches many typo'd
assertions immediately rather than letting them silently no-op. It's still
worth knowing the failure mode existed (you'll see `unsafe=True` in older
codebases working around it, sometimes for legitimate reasons, sometimes
accidentally reintroducing the footgun) — and `autospec`/`spec` give you an
even stronger guarantee, because they constrain the mock to the real
object's *actual* attribute set, typos and all, not just a fixed blocklist of
assert-like prefixes.

## Common Pitfalls

- **Defaulting to un-spec'd `Mock()`/`MagicMock()` for real collaborators.**
  Fine for throwaway objects; risky for anything standing in for a real
  class in your codebase, because the mock will never tell you that your
  code (or your test) is calling a method that doesn't exist or was renamed.
- **Using `MagicMock` when `Mock` would surface a real bug.** If your
  production code should never call `len()` on some object and accidentally
  does, a `MagicMock` masks that (returns `0` silently) where a plain `Mock`
  would raise `TypeError` and catch the bug.
- **Forgetting `spec` doesn't check call signatures.** If argument-shape
  correctness matters (it usually does), you want `autospec`, not `spec`.
- **`side_effect` as an iterable running out mid-test.** If your code under
  test calls the mock more times than you provided values for, you get
  `StopIteration` — sometimes a real signal ("your code calls this more
  than expected"), sometimes just an under-provisioned test fixture. Don't
  reflexively pad the list without first checking which one it is.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/06-unittest-mock/`, create `src/payment_gateway.py` with a
> real `PaymentGateway` class (methods: `charge(amount: float, currency:
> str) -> str` returning a transaction id, `refund(transaction_id: str) ->
> bool`), and a `src/checkout.py` module with a `Checkout` class that takes
> a gateway object in its constructor and has a `pay(amount, currency)`
> method calling `gateway.charge(...)`. Then write
> `tests/test_checkout.py` with: (1) a test using a plain `Mock()` for the
> gateway where I deliberately call a misspelled assertion method
> (`mock_gateway.charge.asert_called_once_with(...)`) so I can observe
> whether it raises `AttributeError` on my Python version or not — add a
> comment asking me to check my Python version and explain why; (2) a
> parallel test using `create_autospec(PaymentGateway, instance=True)`
> where I deliberately call `gateway.charge(10.0)` with a missing argument,
> so I can see the `TypeError` autospec produces that plain `Mock` would
> not have caught; (3) a test using `side_effect` as a list of two values to
> prove a retry-logic method in `Checkout` (add a `pay_with_retry` method
> that tries twice on failure) correctly retries once before succeeding;
> (4) a test using `side_effect` as an exception to prove `pay` propagates a
> `ConnectionError` from the gateway rather than swallowing it. Leave test
> #2 and #4 for me to write from a docstring TODO — pre-write #1 and #3 as
> worked examples.

## Quiz

1. Your production code does `for item in collaborator: ...`. You replace
   `collaborator` with a plain `Mock()` in a test. What happens, and why?
2. What's the difference in what `spec` checks versus what `autospec`
   checks?
3. Write (conceptually) a `side_effect` that makes a mock raise
   `TimeoutError` on its first call and return `"ok"` on every call after
   that.
4. Why can plain, un-spec'd mocks let a misspelled assertion method pass a
   test silently (historically), and what are two different mitigations
   mentioned in this lesson?
5. You need a mock for an object your code only ever passes around and
   never calls, but calling it accidentally would indicate a real bug you
   want caught immediately. Which of `Mock`, `MagicMock`, `NonCallableMock`
   fits best, and why?

<details>
<summary>Answers</summary>

1. It raises `TypeError`, because plain `Mock` does not implement `__iter__`
   (or any other "magic"/dunder method) — those are looked up on the type,
   and `Mock` doesn't define them. You'd need `MagicMock` (which
   preconfigures `__iter__` and other protocol methods) to make the `for`
   loop work.
2. `spec` checks that accessed (and, with `spec_set`, assigned) attribute
   names actually exist on the real object/class — it does not validate how
   callables are invoked. `autospec` (`create_autospec`) does everything
   `spec` does *and* inspects real call signatures, raising `TypeError` if a
   mocked method is called with the wrong number/kind of arguments,
   recursively across nested attributes.
3. Something like
   `side_effect = [TimeoutError("timeout"), "ok", "ok", "ok", ...]` won't
   work forever (finite list) — the idiomatic version is a small function:
   `def _effect(*a, **kw): _effect.calls = getattr(_effect, "calls", 0) + 1; 
   ` with logic to raise on the first call and return `"ok"` thereafter, or
   more simply an iterable exhausted after the first failing call followed
   by enough repeated "ok" entries for however many calls the test expects.
   The key conceptual point: `side_effect` as an exception instance raises
   it; as a callable, its return value (or raised exception) drives each
   call individually, so you can vary behavior across calls with a stateful
   function or itertools-based generator passed as `side_effect`.
4. Historically, plain `Mock` auto-created a new child mock for *any*
   attribute access, including a typo'd assertion name like
   `asert_called_once_with`, so the "assertion" silently did nothing instead
   of raising or failing. Two mitigations: (a) modern `unittest.mock`
   (Python 3.8+) blocks attribute access to names with common
   assert-typo prefixes by default (`unsafe=False`); (b) using `spec` or
   `autospec` constrains the mock to the real object's actual attributes, so
   any name that isn't a real method — typo or not — raises `AttributeError`
   immediately, which is the stronger and more general guarantee.
5. `NonCallableMock` (or `NonCallableMagicMock` if it also needs to support
   protocol methods otherwise) — it preserves normal attribute
   access/spec behavior but raises `TypeError` the moment the code under
   test tries to call the object like a function, which is exactly the bug
   you want surfaced instead of silently tolerated.

</details>

## Further Reading

- Python docs — [`unittest.mock` — mock object library](https://docs.python.org/3/library/unittest.mock.html)
- Python docs — [`unittest.mock` — autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing)
- Python docs — [`unittest.mock` — the `unsafe` parameter](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock)

---
Previous: [05 — Parametrization Mastery](05-parametrization-mastery.md) · Next: [07 — patch() Mechanics & Where to Patch](07-patch-mechanics-and-where-to-patch.md)
