# Lesson 07 — patch() Mechanics & Where to Patch

Phase 3: Mocking Mastery

## Learning Objectives

- Explain, mechanically, what `unittest.mock.patch()` actually does to a
  namespace — not just "it replaces something."
- Correctly apply the "patch where it's looked up, not where it's defined"
  rule to a real, ambiguous import situation.
- Use `patch.object`, `patch.dict`, and `patch.multiple` for their specific,
  narrower use cases.
- Choose between decorator, context-manager, and `mocker.patch` (preview of
  Lesson 09) call styles deliberately.

## Why This Matters in Production

"Patch where it's used, not where it's defined" is a piece of pytest/mock
folklore almost everyone has heard and a smaller number of people can
actually apply correctly under pressure — especially in codebases with
re-exports, `__init__.py` convenience imports, or deeply nested modules. Get
it wrong and you get a test that patches *something*, passes, and tests
nothing real: the code under test keeps calling the original, unpatched
function, and your assertion about "the mock was called" either fails
confusingly or — worse — the test doesn't assert on the mock at all and just
silently exercises live code (a real network call, a real file write) inside
what everyone believes is a unit test.

## Concept: What `patch()` Actually Does

`patch()` does **name rebinding in a namespace**, not "magic that finds
every reference to a function anywhere in memory." Concretely, when you
write:

```python
patch("mymodule.some_function")
```

mock does the equivalent of:

```python
import mymodule
original = mymodule.some_function
mymodule.some_function = Mock()
# ...test runs...
mymodule.some_function = original   # restored on exit
```

It looks up the attribute `some_function` on the object `mymodule` (its
module namespace) and replaces that attribute with a `MagicMock` for the
duration of the patch, restoring the original afterward. Nothing about this
touches any other name that happens to refer to the same underlying function
object elsewhere.

## Concept: "Patch Where It's Looked Up"

This is the direct, mechanical consequence of the above. Consider:

```python
# gateway.py
def charge_card(amount):
    ...

# checkout.py
from gateway import charge_card

def process_order(amount):
    return charge_card(amount)
```

After `from gateway import charge_card`, the name `charge_card` inside
`checkout.py`'s namespace is its **own independent binding** to the same
function object — not a live reference back to `gateway.charge_card`.
`checkout.py`'s module dict has an entry `"charge_card"` pointing at the
function; so does `gateway.py`'s. They started out pointing at the same
object, but they are two separate names in two separate namespaces.

So:

```python
@patch("gateway.charge_card")     # WRONG for this test
def test_process_order(mock_charge):
    process_order(100)
    mock_charge.assert_called_once_with(100)   # FAILS
```

This patches `gateway.charge_card` — but `process_order` never looks up
`gateway.charge_card` at call time; it calls the local name `charge_card` in
`checkout.py`'s own namespace, which still points at the *original*
function, because that binding was never touched.

```python
@patch("checkout.charge_card")    # CORRECT
def test_process_order(mock_charge):
    process_order(100)
    mock_charge.assert_called_once_with(100)   # PASSES
```

The rule, stated mechanically rather than as folklore: **patch the name in
the namespace where the code under test will look it up at call time** —
which is wherever the `import` statement bound it, not wherever it was
originally defined. If `checkout.py` had instead done `import gateway` and
called `gateway.charge_card(amount)`, then `patch("gateway.charge_card")`
*would* be correct, because in that case `checkout.py` looks the attribute
up on the `gateway` module object at call time, rather than using a local
name bound at import time.

**The practical test**: ask "what does the line of code that calls this
function actually evaluate, at the moment it runs, to find the callable?"
Whatever namespace-and-attribute path answers that question is what you
patch.

## Concept: `patch.object`

When you already have a reference to the object/class/module and want to
patch one of its attributes, `patch.object` is more explicit and less
error-prone than building a dotted-string path by hand:

```python
from unittest.mock import patch
import checkout

with patch.object(checkout, "charge_card") as mock_charge:
    checkout.process_order(100)
    mock_charge.assert_called_once_with(100)
```

This is equivalent to `patch("checkout.charge_card")` but avoids a subtle
class of bugs where the string path has a typo that doesn't get caught until
runtime (or, worse, silently patches nothing if it targets an attribute that
doesn't exist yet under some conditions). It's also the natural choice when
patching a method on a specific instance rather than a class-level or
module-level name.

## Concept: `patch.dict` and `patch.multiple`

`patch.dict` temporarily modifies a dictionary (commonly `os.environ`) and
restores it afterward:

```python
import os
from unittest.mock import patch

with patch.dict(os.environ, {"API_KEY": "test-key-123"}):
    assert os.environ["API_KEY"] == "test-key-123"
# original os.environ contents (including whether API_KEY existed at all)
# are restored here
```

Compare this to Lesson 08's `monkeypatch.setenv` — they solve the same
problem; which one you reach for is often a house-style choice (see that
lesson for the tradeoffs).

`patch.multiple` patches several attributes on the same target in one call,
useful when you'd otherwise stack three or four `@patch` decorators on one
test:

```python
with patch.multiple(
    "checkout",
    charge_card=DEFAULT,
    send_receipt=DEFAULT,
):
    ...
```

Using the `DEFAULT` sentinel tells `patch.multiple` "auto-create a
`MagicMock` for this one, and give it to me" — same as an ordinary `patch`
would, just batched.

## Concept: Decorator vs Context Manager vs Fixture

```python
@patch("checkout.charge_card")            # decorator: whole test function
def test_a(mock_charge):
    ...

def test_b():
    with patch("checkout.charge_card") as mock_charge:   # context manager: scoped block
        ...

def test_c(mocker):                        # pytest-mock fixture (Lesson 09)
    mock_charge = mocker.patch("checkout.charge_card")
    ...
```

All three do the same underlying rebind-and-restore. The differences are
ergonomic: the decorator applies for the whole test and stacks awkwardly
(each additional `@patch` adds a parameter, and — subtly — **decorator
order is bottom-up**: the closest decorator to the function corresponds to
the first mock parameter). The context manager is more explicit about scope
when you only want part of a test patched. `mocker.patch` (Lesson 09) gets
you automatic cleanup without either the decorator's parameter-ordering
gotcha or a manual context manager block, which is why it tends to win as
house style once a codebase has pytest-mock available.

## Common Pitfalls

- **Patching where a function is *defined* instead of where it's *looked
  up*, because that's the "obvious" string to reach for.** This is the
  single most common `patch()` mistake in real codebases — see the worked
  example above.
- **Stacking multiple `@patch` decorators and getting the mock parameter
  order backwards.** Decorators apply bottom-up, so the mock for the
  *closest* decorator to the function signature comes *first* in the
  parameter list. Miscounting this silently swaps which mock is which,
  and both mocks being `MagicMock` means nothing type-checks to catch it.
- **Patching an entire module (`patch("requests")`) when you only need one
  function.** Broad patches make it easy to accidentally leave other calls
  on that module un-mocked and hitting real code (or worse, real IO) without
  the test author noticing — patch the narrowest thing that's actually true
  to what the code under test calls.
- **Forgetting `patch()` restores state even on test failure — but only if
  it was actually entered/applied.** If setup code before a `with patch(...)`
  block raises, the patch never took effect and there's nothing to restore
  — usually fine, but worth knowing when debugging "why didn't the patch
  apply" in a test with early-exit logic.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/07-patch-mechanics/`, create three files that reproduce the
> canonical "patch where it's used" trap on purpose: `src/email_service.py`
> with a function `send_email(to, subject)`, `src/signup.py` that does
> `from email_service import send_email` and calls it inside a
> `register_user(email)` function, and `src/signup_alt.py` that instead does
> `import email_service` and calls `email_service.send_email(...)` inside an
> equivalent `register_user_alt(email)` function. Then write
> `tests/test_signup.py` with four tests: two that patch
> `"email_service.send_email"` against `register_user` (this should FAIL —
> leave a comment predicting why before I run it) and against
> `register_user_alt` (this should PASS), and two more that patch
> `"signup.send_email"` against `register_user` (PASS) and
> `"signup_alt.email_service.send_email"` against `register_user_alt`
> (PASS). I want to run all four, see exactly one fail, and write in my own
> words in a comment why the pattern (`from x import y` vs `import x`)
> changes which patch target is correct. Also add one `patch.dict` example
> temporarily setting an env var consumed by a small function in
> `signup.py`, restoring afterward — assert the env var is gone again after
> the `with` block exits.

## Quiz

1. In one sentence, what does `patch("module.name")` actually do to Python
   at runtime?
2. Module `a.py` defines `def helper(): ...`. Module `b.py` does
   `from a import helper` and calls `helper()` inside a function. You want
   to mock `helper` for a test of that function in `b.py`. What string do
   you pass to `patch()`, and why not `"a.helper"`?
3. If `b.py` had instead done `import a` and called `a.helper()`, would
   `patch("a.helper")` now be correct? Why does the import style change the
   answer?
4. You stack two decorators: `@patch("mod.foo")` above `@patch("mod.bar")`
   directly above a test function `def test_x(mock_bar, mock_foo):`. Is the
   parameter order shown here correct? Explain the rule.
5. When would `patch.object(some_module, "some_attr")` be preferable to
   `patch("package.some_module.some_attr")` as a string?

<details>
<summary>Answers</summary>

1. It looks up the attribute named after the last dot on the object/module
   named by everything before it, replaces that attribute with a
   `MagicMock` (or a specified replacement) for the duration of the patch,
   and restores the original value when the patch exits (decorator returns,
   context manager block ends, or fixture teardown runs).
2. `patch("b.helper")` — because `from a import helper` creates an
   independent name `helper` inside `b.py`'s own namespace at import time.
   The function inside `b.py` looks up `helper` in `b.py`'s namespace when
   it's called, not in `a.py`'s. Patching `"a.helper"` changes a name that
   `b.py`'s code never consults again after the initial import.
3. Yes, `patch("a.helper")` would now be correct — because `b.py`'s function
   calls `a.helper()`, which looks the attribute `helper` up on the `a`
   module object *at call time*, every time it's called. Since `patch`
   rebinds that exact attribute on that exact module object, the lookup at
   call time sees the mock. The import style determines whether the calling
   code re-reads the target module's namespace on every call (`import a` /
   `a.helper()`) or captured a private, independent binding once at import
   time (`from a import helper`).
4. No — it's backwards. Decorators apply bottom-up (closest to the function
   is applied first / corresponds to the mock passed in first), so
   `@patch("mod.bar")` (the one directly above the function) corresponds to
   the *first* mock parameter, and `@patch("mod.foo")` (further above)
   corresponds to the *second*. The correct signature for the order shown
   is `def test_x(mock_bar, mock_foo):` matching bottom-to-top, which is
   what's given — so actually this is correct as written; the trap is
   assuming top-to-bottom and getting it backwards, which is worth
   double-checking any time more than one `@patch` decorator stacks.
5. When you already hold a reference to the target object/module in the
   test (or it's more convenient to import it directly) rather than
   constructing a dotted string path by hand — `patch.object` avoids typos
   in long dotted paths and fails fast/obviously (an `AttributeError` at
   patch time) if the attribute name is wrong, whereas a subtly wrong string
   path can sometimes fail in more confusing ways depending on what's on
   that path.

</details>

## Further Reading

- Python docs — [`unittest.mock.patch`](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.patch)
- Python docs — [`patch.object`, `patch.dict`, `patch.multiple`](https://docs.python.org/3/library/unittest.mock.html#patch-object)
- Python docs — [Where to patch](https://docs.python.org/3/library/unittest.mock.html#where-to-patch)

---
Previous: [06 — unittest.mock Deep Dive](06-unittest-mock-deep-dive.md) · Next: [08 — monkeypatch vs mock.patch](08-monkeypatch-vs-mock-patch.md)
