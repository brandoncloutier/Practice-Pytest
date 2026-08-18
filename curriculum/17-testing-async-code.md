# Lesson 17 — Testing Async Code

Phase 5: Testing Real-World Systems

## Learning Objectives

- Configure and use `pytest-asyncio` to run `async def` test functions.
- Explain the difference between `asyncio_mode = "strict"` and `"auto"`,
  and pick one deliberately for a codebase.
- Use `unittest.mock.AsyncMock` correctly, and explain why a plain `Mock`
  breaks when standing in for an `async def` collaborator.
- Write and use async fixtures.

## Why This Matters in Production

Async Python is now common in production services (web frameworks, I/O-bound
clients, job queues), and testing it wrong is easy in a specific, recurring
way: using a plain `Mock`/`MagicMock` where an `AsyncMock` was needed. It
often doesn't fail loudly — depending on how the mock is awaited, you can
get a confusing `TypeError` far from the actual mistake, or in some cases a
test that "passes" without actually awaiting anything meaningful. This
lesson closes that specific gap and gets you comfortable with the
async-specific pytest machinery you need on top of everything from Phases
1–4, which otherwise applies unchanged.

## Concept: Configuring `pytest-asyncio`

```python
# pip install pytest-asyncio
import asyncio
import pytest

@pytest.mark.asyncio
async def test_fetch_returns_data():
    result = await fetch_data()
    assert result == {"status": "ok"}
```

Without configuration, `pytest-asyncio` requires **strict mode** by default
— every async test needs an explicit `@pytest.mark.asyncio` marker, or
pytest will collect the test but it'll be silently skipped (or reported with
a warning depending on version) because pytest doesn't natively know how to
run a coroutine as a test. This explicitness is a deliberate design choice:
it's obvious, from reading a test file, which tests are async and require
the plugin's involvement.

**Auto mode** removes the need for the marker on every test, at the cost of
that explicitness:

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

With `auto`, any `async def test_*` function is automatically treated as an
async test — no marker needed. **Production guidance**: for a codebase that
is substantially or entirely async, `auto` mode reduces boilerplate with
little real cost (a reader can tell a test is async from the `async def`
keyword itself). For a codebase with only occasional async tests mixed into
a mostly-sync suite, `strict` mode's explicit marker is arguably a better
signal — it makes the exceptional case visibly exceptional. Either is
legitimate; pick one per-project and be consistent, the same way Lesson 08
recommended for `monkeypatch` vs `mocker`.

## Concept: `AsyncMock`

This is the concept most worth internalizing from this lesson. `unittest.
mock` (since Python 3.8) provides `AsyncMock`, specifically designed to
stand in for `async def` functions/methods — calling it returns a coroutine
that, when awaited, produces the configured return value:

```python
from unittest.mock import AsyncMock

async def test_notify_calls_async_client(mocker):
    mock_client = mocker.AsyncMock()      # pytest-mock exposes this too
    mock_client.send.return_value = {"delivered": True}

    result = await notify(mock_client, "hello")

    mock_client.send.assert_awaited_once_with("hello")
    assert result == {"delivered": True}
```

Compare to what happens with a plain `Mock`/`MagicMock` standing in for an
async collaborator:

```python
async def notify(client, message):
    return await client.send(message)   # code under test awaits the mock's return

mock_client = Mock()
mock_client.send.return_value = {"delivered": True}
await notify(mock_client, "hello")
# TypeError: object dict can't be used in 'await' expression
```

`Mock().send(...)` returns a plain `Mock` (or whatever `return_value` you
configured) directly — not a coroutine — so `await`ing it fails, because
there's nothing awaitable there. `AsyncMock().send(...)` returns a real
coroutine object under the hood, which `await` can correctly consume,
ultimately producing the configured `return_value`. If you patch a real
`async def` method with `patch()`/`mocker.patch()` and the target is
correctly detected as a coroutine function, modern `unittest.mock`
**auto-detects this and uses `AsyncMock` automatically** — but this
detection depends on `patch` being able to introspect the real target, which
is exactly why `autospec`/`spec` (Lesson 06) matters even more for async
code: without a spec pointing at the real async method, `patch()` can't
always tell it should produce an `AsyncMock` instead of a plain one, and the
`TypeError` above is what tells you it guessed wrong (or that you built a
bare `Mock()` yourself without going through `patch` at all).

`AsyncMock` also gives you async-specific assertion methods:
`assert_awaited()`, `assert_awaited_once()`, `assert_awaited_with(...)`,
`assert_awaited_once_with(...)` — parallel to the `assert_called_*` family,
but specifically checking that the mock was actually *awaited*, not merely
called (a mock can be called without being awaited if the caller forgot the
`await` keyword — a real bug `assert_awaited` catches that `assert_called`
would not).

## Concept: Async Fixtures

`pytest-asyncio` supports `async def` fixtures directly:

```python
@pytest.fixture
async def async_db_connection():
    conn = await connect_async_db()
    yield conn
    await conn.close()

async def test_query_returns_rows(async_db_connection):
    rows = await async_db_connection.fetch("SELECT 1")
    assert rows
```

Same shape as every synchronous fixture from Phase 2 — scopes, composition,
`conftest.py` layering, factory-as-fixture — all apply unchanged; the only
difference is `async def`/`await` in the fixture body for genuinely
asynchronous setup/teardown (an async connection pool, an async HTTP
client's own startup/shutdown lifecycle). Sync and async fixtures can be
mixed and can depend on each other in either direction as long as the
plugin's event loop handling supports it for your configuration — check
`pytest-asyncio`'s docs for the current details on event-loop-scoped
fixtures if you hit an edge case here, since event loop lifecycle handling
is one of the areas that's evolved across `pytest-asyncio` versions.

## Common Pitfalls

- **Using a plain `Mock`/`MagicMock` for an async collaborator.** The
  `TypeError` you get (`object X can't be used in 'await' expression`) is
  usually the first sign — if you see it in an async test, check whether
  you needed `AsyncMock` instead.
- **Forgetting `asyncio_mode` configuration entirely and being confused
  when async tests silently don't run as expected.** Check your project's
  `pytest.ini`/`pyproject.toml` for `asyncio_mode` before assuming a bug in
  your test.
- **Asserting `assert_called_once()` instead of `assert_awaited_once()`
  on an `AsyncMock`.** `assert_called_once` only checks the mock was
  invoked, not that the coroutine it returned was ever actually awaited —
  a caller that calls but forgets to `await` a coroutine is a real bug
  (the operation never actually completes), and only the `_awaited_`
  family of assertions catches it.
- **Mixing sync test code that calls `asyncio.run()` manually inside a
  test, instead of using `pytest-asyncio`'s test/fixture support.** Works in
  isolation but doesn't compose with async fixtures, and reintroduces event
  loop management the plugin exists specifically to handle correctly for
  you.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/17-testing-async/`, create `src/notification_service.py`
> with an `async def notify_user(client, user_id: int, message: str) ->
> bool` function that calls `await client.send(user_id, message)` and
> returns whether the client reported success (assume the client's `.send`
> returns a dict like `{"delivered": bool}`), raising a custom
> `NotificationError` if `client.send` raises. Set up `pyproject.toml` in
> this exercise folder with `asyncio_mode = "auto"` and add `pytest-asyncio`
> to a `requirements-dev.txt`, pinned to a real current version. Write
> `tests/test_notification_service.py` with: (1) a correct test using
> `mocker.AsyncMock()` (or `unittest.mock.AsyncMock` directly — try both
> and note if there's any difference) with `assert_awaited_once_with(...)`;
> (2) a DELIBERATELY BROKEN test using a plain `mocker.Mock()` instead,
> left for me to run first and observe the `TypeError`, with a comment
> asking me to explain in my own words why it happens before fixing it
> myself to use `AsyncMock`; (3) a test simulating `client.send` raising an
> exception (via `AsyncMock(side_effect=ConnectionError(...))`) and
> asserting `NotificationError` propagates instead; (4) an async fixture
> (`async def` with `yield`) providing a pre-configured `AsyncMock` client,
> used by at least two of the above tests, to demonstrate async fixture
> composition. Don't fix item (2) for me — leave it broken with the
> explanatory comment as the exercise.

## Quiz

1. What does `pytest-asyncio`'s `strict` mode require on every async test
   that `auto` mode does not?
2. `notify(client, msg)` does `return await client.send(msg)`. In a test,
   you set `mock_client = Mock(); mock_client.send.return_value = {"ok":
   True}`. What specifically goes wrong when the test runs, and why?
3. What's the difference between what `assert_called_once()` and
   `assert_awaited_once()` each verify on an `AsyncMock`, and give a
   concrete bug that only the second one would catch?
4. Under what condition does `patch()`/`mocker.patch()` correctly
   auto-select `AsyncMock` instead of a plain `MagicMock` for you, and why
   does that make `autospec`/`spec` more important for async code
   specifically?
5. True or false: async fixtures require completely different scope and
   composition rules from sync fixtures. Briefly justify.

<details>
<summary>Answers</summary>

1. `strict` mode requires every async test function to be explicitly
   marked with `@pytest.mark.asyncio`; without the marker, pytest doesn't
   know to run it as an async test. `auto` mode removes that requirement —
   any `async def test_*` function is automatically treated as an async
   test with no marker needed.
2. `mock_client.send(msg)` returns the plain dict `{"ok": True}` directly
   (that's what `return_value` was set to) — not a coroutine. `await`ing a
   plain dict raises `TypeError: object dict can't be used in 'await'
   expression`, because a plain `Mock`'s calls don't produce awaitable
   objects; only `AsyncMock`'s calls do (they return a real coroutine that,
   when awaited, yields the configured `return_value`).
3. `assert_called_once()` only verifies the mock was invoked (called)
   exactly once — it says nothing about whether the coroutine that call
   produced was ever actually awaited. `assert_awaited_once()` verifies it
   was both called and actually awaited exactly once. The bug it uniquely
   catches: code that calls an async function but forgets the `await`
   keyword (e.g., `client.send(msg)` instead of `await client.send(msg)`)
   — the call happens, so `assert_called_once()` would pass, but the actual
   operation never completes, and only `assert_awaited_once()` would flag
   that as wrong.
4. It auto-selects `AsyncMock` when `patch()` can introspect the real
   target being replaced and determine it's a coroutine function (an
   `async def`) — which depends on `patch` actually being able to see the
   real object's definition. This is exactly why `spec`/`autospec` matters
   more here: without a spec tying the mock to the real async method,
   there's more room for `patch()` to be unable to make that determination
   correctly (or for a hand-built bare `Mock()`, bypassing `patch`
   entirely, to never get this auto-detection at all), leading straight
   back to the `TypeError` from question 2.
5. False. Async fixtures use the same scope levels (`function`, `class`,
   `module`, `package`, `session`), the same composition rules (fixtures
   depending on other fixtures), and the same `conftest.py` discovery and
   overriding rules as sync fixtures — the only difference is `async def`
   plus `await` inside the fixture body for genuinely asynchronous
   setup/teardown work. Event-loop-specific scoping details are a real,
   evolving nuance worth checking current `pytest-asyncio` docs for, but
   they don't replace or contradict the general fixture model from Phase 2.

</details>

## Further Reading

- pytest-asyncio docs — [PyPI project page and configuration](https://pypi.org/project/pytest-asyncio/)
- Python docs — [`unittest.mock.AsyncMock`](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock)
- Python docs — [`asyncio` — coroutines and tasks (background for what's actually being awaited)](https://docs.python.org/3/library/asyncio-task.html)

---
Previous: [16 — Testing Databases & Persistence](16-testing-databases-and-persistence.md) · Next: [18 — Property-Based Testing with Hypothesis](18-property-based-testing-with-hypothesis.md)
