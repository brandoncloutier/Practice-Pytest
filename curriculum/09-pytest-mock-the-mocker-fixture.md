# Lesson 09 — pytest-mock (the mocker fixture)

Phase 3: Mocking Mastery

## Learning Objectives

- Explain what `pytest-mock`'s `mocker` fixture is (and isn't) relative to
  `unittest.mock`.
- Use `mocker.patch`, `mocker.patch.object`, `mocker.patch.dict`, and
  `mocker.spy` idiomatically.
- Explain why `mocker` needs no manual cleanup, and what mechanism provides
  that.
- Use `mocker.spy` to assert on a *real* function's calls without replacing
  its behavior — the one capability plain `Mock`/`patch` doesn't give you as
  directly.

## Why This Matters in Production

`pytest-mock` is a thin wrapper — its own docs describe the `mocker` fixture
as "a thin-wrapper around the patching API provided by the `mock` package."
It's popular in production codebases for one practical reason: it turns
`mock.patch`'s decorator/context-manager ergonomics into a fixture, which
composes with the rest of pytest the same way every other fixture does, and
which cleans up automatically without you needing to think about `with`
blocks or decorator stacking order (Lesson 07's parameter-ordering footgun
disappears entirely). If your team already has `pytest-mock` installed,
knowing it well is often higher-leverage day to day than knowing raw
`unittest.mock` syntax — though everything you learned in Lessons 06–07
transfers directly, because `mocker` isn't a different mocking system, it's
the same one with better pytest integration.

## Concept: `mocker` Is a Fixture Wrapping `unittest.mock`

```python
def test_charge_calls_gateway(mocker):
    mock_charge = mocker.patch("checkout.charge_card")
    process_order(100)
    mock_charge.assert_called_once_with(100)
```

Compare this to the decorator form from Lesson 07 — same target string,
same "patch where it's looked up" rule applies unchanged, same `MagicMock`
returned, same assertion methods available. The only thing that changed is
*how* the patch gets applied and cleaned up: as a fixture method call
instead of a decorator or `with` block.

```python
def test_multiple_patches(mocker):
    mock_charge = mocker.patch("checkout.charge_card")
    mock_receipt = mocker.patch("checkout.send_receipt")
    process_order(100)
    mock_charge.assert_called_once_with(100)
    mock_receipt.assert_called_once()
```

No decorator stacking, no bottom-up ordering to track — each `mocker.patch`
call returns its own mock directly, in the order you called them, which
avoids Lesson 07's easiest-to-get-wrong footgun entirely.

`mocker` also exposes the rest of the family you'd expect:
`mocker.patch.object(...)`, `mocker.patch.dict(...)`, `mocker.patch.
multiple(...)` — same semantics as their `unittest.mock` counterparts,
same target-resolution rules, just fixture-shaped.

## Concept: Automatic Cleanup — and Why It's Safe

Every patch applied through `mocker` is automatically undone after the test,
same guarantee as `monkeypatch`, and for the same underlying reason: `mocker`
is itself a `function`-scoped pytest fixture, so its teardown (unpatching
everything it patched) runs via the normal fixture finalization machinery
from Lesson 02–03. You do not need `addCleanup`, a `finally` block, or a
manual `mocker.stopall()` call in the common case — it happens for you,
which is the whole ergonomic win over managing `with patch(...):` blocks by
hand for every mock in a test with several collaborators to isolate.

## Concept: `mocker.spy` — Assert Without Replacing Behavior

This is the one capability in this lesson that isn't just "the same thing,
nicer syntax." A **spy** wraps a *real* function/method — calls still go
through to the real implementation — while recording call information you
can assert against afterward:

```python
def test_process_order_logs_correctly(mocker):
    spy = mocker.spy(logger, "info")
    process_order(100)
    spy.assert_called_once_with("Order processed: $100")
    # logger.info() still actually ran — real logging still happened
```

This matters because it's a different testing *intent* than `mocker.patch`.
Patching replaces behavior — you use it when the real implementation is
something you deliberately don't want running in a unit test (a network
call, a slow computation, a side effect on shared state). Spying observes
behavior without changing it — you use it when the real implementation is
safe and correct to actually run, and what you want to verify is simply
*that it was called, and with what*. Reaching for `patch` when you actually
wanted a spy is a common way tests end up asserting nothing meaningful: you
replace the function, assert your replacement was called (trivially true
since you called it), and never actually exercise the real logic you meant
to be testing.

## Concept: `mocker` vs Raw `unittest.mock` — What You Actually Gain

To be precise about the scope of this lesson: `pytest-mock` does not give
you new mocking *capabilities* beyond `unittest.mock` — `Mock`, `MagicMock`,
`spec`, `autospec`, `side_effect`, all of Lesson 06 and 07 apply unchanged,
because `mocker.patch(...)` calls straight through to `unittest.mock.patch`
under the hood. What you gain is:

1. **No manual cleanup bookkeeping** — fixture teardown handles it.
2. **No decorator-stacking parameter-order footgun** — each call returns its
   own mock directly.
3. **`mocker.spy`**, a convenience over manually constructing a
   `Mock(wraps=real_function)` (which is possible in raw `unittest.mock` but
   more verbose and less commonly reached for).
4. **Consistency with the rest of your fixture-based test setup** — `mocker`
   composes with other fixtures the way `db_session`, `api_client`, etc. do,
   rather than being a different kind of thing (a decorator) bolted onto a
   fixture-based test.

## Common Pitfalls

- **Reaching for `mocker.patch` when `mocker.spy` is what the test actually
  needs.** If you find yourself patching a pure, safe, fast function purely
  so you can assert it was called — and you'd have been fine letting it
  actually run — that's a spy, not a patch.
- **Assuming `mocker` gives you something `unittest.mock` fundamentally
  can't.** It doesn't; conflating "pytest-mock" with "a different mocking
  library" leads to confusion when reading `unittest.mock` documentation
  (which fully applies) or when a codebase mixes both styles.
- **Forgetting `mocker` is function-scoped by default**, and being surprised
  a patch applied inside a `session`-scoped fixture that used `mocker`
  doesn't behave the way you'd expect — `mocker`'s own fixture scope governs
  when its patches are undone, which can create a scope mismatch (Lesson 03)
  if you're not careful about which fixture requests it.
- **Not checking whether `pytest-mock` is actually a project dependency**
  before writing `mocker`-based tests — unlike `monkeypatch` (built into
  pytest itself), `mocker` requires the `pytest-mock` package to be
  installed. A codebase without it will fail collection with a fixture-not-
  found error, not a helpful "please install pytest-mock" message.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/09-pytest-mock/`, reuse or rebuild a small `src/checkout.py`
> (a `process_order(amount)` function calling a `gateway.charge_card` and a
> module-level `logging.getLogger(__name__)` call to log
> `f"Order processed: ${amount}"`). Write `tests/test_checkout.py` with:
> (1) a `mocker.patch` test asserting `charge_card` was called correctly
> (same target-resolution rules as Lesson 07 apply — patch where it's
> looked up); (2) a `mocker.spy` test on the logger's `.info` method proving
> the real logging call still happened (capture it with `caplog` — look up
> what that built-in fixture does — to prove the message content, not just
> that the spy was called); (3) a test that patches *two* collaborators in
> one test with two separate `mocker.patch` calls, to contrast with Lesson
> 07's decorator-stacking example — add a comment noting there's no
> parameter-order concern here, unlike the decorator version; (4) confirm in
> a short comment that pytest-mock is declared as a dependency (check for a
> `requirements.txt` or `pyproject.toml` in this exercise folder — add one
> with `pytest-mock` pinned to a real current version if it's missing).

## Quiz

1. Precisely what does `mocker.patch("x.y")` do differently, mechanically,
   from `unittest.mock.patch("x.y")`?
2. Why does `mocker` not require `addCleanup` or a manual `stopall()` call
   in ordinary use?
3. You want to verify a real caching function was actually invoked and
   actually populated the cache, without faking its behavior. Is `mocker.
   patch` or `mocker.spy` the right tool, and why?
4. A teammate says "we don't need `unittest.mock` docs anymore, we use
   pytest-mock." What's wrong with that framing?
5. What real dependency requirement does `mocker` have that `monkeypatch`
   does not, and what's the practical consequence of forgetting it?

<details>
<summary>Answers</summary>

1. Nothing different in the underlying patching mechanism — `mocker.patch`
   calls through to `unittest.mock.patch` and performs the exact same
   namespace rebind-and-restore described in Lesson 07. The difference is
   *how* it's invoked (as a method on a pytest fixture rather than a
   decorator/context manager) and *how* it's cleaned up (via pytest fixture
   teardown rather than the decorator/context-manager's own exit logic).
2. Because `mocker` is itself a `function`-scoped pytest fixture. Its
   teardown code (which undoes every patch it applied during the test) runs
   automatically as part of normal pytest fixture finalization — the same
   mechanism that gives `yield` fixtures guaranteed cleanup in Lessons 02–03
   — so there's no separate cleanup registration needed.
3. `mocker.spy` — because the goal is to observe a real call (and its real
   effect on the cache) rather than replace it with fake behavior. `mocker.
   patch` would substitute a `MagicMock` in its place, meaning the real
   caching logic would never actually run, and you'd only be proving that
   your test called a mock, not that the real function does what you think.
4. `pytest-mock` doesn't replace `unittest.mock` — it's a thin wrapper
   around it, and every concept from `unittest.mock` (`Mock`, `MagicMock`,
   `spec`/`autospec`, `side_effect`, the "patch where it's used" rule)
   applies unchanged when working with `mocker`. `unittest.mock`'s docs
   remain the authoritative reference for what a mock *does*; pytest-mock's
   docs are about the *fixture ergonomics* layered on top.
5. `mocker` requires the third-party `pytest-mock` package to be installed;
   `monkeypatch` ships as part of pytest itself and needs nothing extra. If
   a codebase or CI environment is missing `pytest-mock`, tests requesting
   the `mocker` fixture will fail at collection/setup with a "fixture
   'mocker' not found" error rather than any more specific installation
   hint — worth knowing so you check `pyproject.toml`/`requirements.txt`
   first rather than assuming a code bug.

</details>

## Further Reading

- pytest-mock docs — [PyPI project page and usage](https://pypi.org/project/pytest-mock/)
- pytest-mock docs — [Full usage reference (readthedocs)](https://pytest-mock.readthedocs.io/en/latest/usage.html)
- Python docs — [`unittest.mock` — `Mock(wraps=...)` (what `spy` builds on)](https://docs.python.org/3/library/unittest.mock.html#calling)

---
Previous: [08 — monkeypatch vs mock.patch](08-monkeypatch-vs-mock-patch.md) · Next: [10 — Test Doubles Strategy](10-test-doubles-strategy.md)
