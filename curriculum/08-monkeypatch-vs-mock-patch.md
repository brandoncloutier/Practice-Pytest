# Lesson 08 — monkeypatch vs mock.patch

Phase 3: Mocking Mastery

## Learning Objectives

- List `monkeypatch`'s full method surface and what each one is for.
- Articulate the actual difference between `monkeypatch` and `mock.patch` —
  it is smaller than most people think.
- Choose deliberately between them for a given situation instead of by
  habit.
- Use `monkeypatch.context()` to scope a patch narrower than a whole test.

## Why This Matters in Production

You already use both tools. The honest answer to "which one should I use"
is: for plain attribute replacement, **it barely matters** — they do
overlapping things, and most of what separates them in real codebases is
house style, not technical necessity. What *does* matter is knowing the
handful of things each one does that the other genuinely can't (or can't do
as cleanly), so you're not reaching for `mock.patch` to set an environment
variable and writing more code than `monkeypatch.setenv` would need, or
reaching for `monkeypatch.setattr` when you actually need call assertions
that only a `Mock` object provides.

## Concept: monkeypatch's Full Method Surface

`monkeypatch` is a pytest **fixture** (not a class you instantiate) with
automatic, guaranteed teardown — "all modifications will be undone after the
requesting test function or fixture has finished," per pytest's own docs.
Its methods:

| Method | Purpose |
|---|---|
| `setattr(obj, name, value, raising=True)` | Replace an attribute with a new value |
| `delattr(obj, name, raising=True)` | Remove an attribute |
| `setitem(mapping, name, value)` | Set a dict-like item |
| `delitem(mapping, name, raising=True)` | Remove a dict-like item |
| `setenv(name, value, prepend=None)` | Set an environment variable |
| `delenv(name, raising=True)` | Delete an environment variable |
| `syspath_prepend(path)` | Prepend to `sys.path` (for import shenanigans) |
| `chdir(path)` | Change the process's working directory |
| `context()` | Apply patches within a narrower `with` block instead of the whole test |

```python
def test_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-123")
    assert load_api_key() == "test-key-123"

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(KeyError):
        load_api_key()
```

The `raising` parameter (on `setattr`/`delattr`/`delitem`/`delenv`) controls
whether pytest raises if the target doesn't already exist — useful for
`delenv` in particular, where you often don't know (or don't want to assume)
whether a given test environment already has that variable set.

## Concept: What's Actually Different from mock.patch

Both `monkeypatch.setattr(obj, "name", value)` and
`patch.object(obj, "name", value)` do fundamentally the same rebind-and-
restore operation described in Lesson 07. The real differences:

**1. `monkeypatch` is a fixture; `mock.patch` is a decorator/context
manager.** This is mostly ergonomic — `monkeypatch` composes naturally with
other fixtures and doesn't need a `with` block or decorator stacking. If a
test already takes five fixture parameters, adding `monkeypatch` as a sixth
is more idiomatic pytest style than nesting a nested `with patch(...):`
block inside the test body.

**2. `monkeypatch` doesn't create a `Mock` object for you.** `monkeypatch.
setattr(obj, "charge", some_replacement)` requires *you* to supply
`some_replacement` — often a plain function, a lambda, or a `Mock()` you
construct yourself. `mock.patch("obj.charge")` with no replacement argument
auto-creates a `MagicMock` and hands it to you. If you need call assertions
(`assert_called_once_with`, etc.), you'll typically pass a `Mock()` instance
to `monkeypatch.setattr` explicitly to get the same capability — at which
point you're using `unittest.mock`'s `Mock` class either way, just choosing
which tool wires it into the target.

**3. `monkeypatch` natively covers environment variables, `sys.path`, and
`chdir` — things `mock.patch` can technically do but more awkwardly.**
`patch.dict(os.environ, {...})` gets you the environment variable case, but
`monkeypatch.setenv`/`delenv` reads more directly as "what this test is
doing." There's no `mock.patch` equivalent that reads as cleanly for
`chdir` or `sys.path` manipulation — those are monkeypatch's clearest wins.

**4. `monkeypatch.context()` scopes a patch to part of a test, restoring
immediately after the `with` block — inside a single test that already has
`monkeypatch` injected.** This matters specifically for the case pytest's
own docs call out: patching something in the standard library or a
third-party library that pytest itself depends on. Leaving such a patch
active for a whole test risks breaking pytest's own internals for the rest
of that test's execution; scoping it narrowly with `context()` avoids that:

```python
def test_something(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(os, "getcwd", lambda: "/fake/path")
        assert get_working_directory_label() == "/fake/path"
    # os.getcwd is back to normal here, for the rest of the test
```

## Concept: A Practical Decision Rule

Given the overlap, a workable house rule:

- **Environment variables, `sys.path`, `chdir`, or a simple attribute swap
  with no need for call assertions** → `monkeypatch`. It's less code and
  reads more intention-revealing for these specific cases.
- **You need call assertions (`assert_called_with`, call counts), `spec`/
  `autospec` behavior, or `side_effect` sequencing** → `mock.patch` (or
  `mocker.patch`, Lesson 09) — you're going to end up holding a `Mock`
  object either way, so let the tool that's built around `Mock` construct
  and wire it for you.
- **You're patching something pytest itself might depend on, and only need
  it patched for part of one test** → `monkeypatch.context()`.

Many teams standardize on `mocker` (Lesson 09) for nearly everything simply
for consistency, and use `monkeypatch` specifically for its env/path/cwd
methods where it has no real substitute. Both are legitimate; what matters
is that your team has *a* consistent answer, not that you memorize the "one
true" rule — a mixed codebase where some files use `monkeypatch.setattr` and
others use `mocker.patch` for the identical situation is a code review smell
worth raising, not because either is wrong, but because the inconsistency
itself costs readers time.

## Common Pitfalls

- **Using `monkeypatch.setattr` and expecting `assert_called_once_with` to
  work on the plain replacement value you passed in.** If you passed a bare
  function or lambda instead of a `Mock`, there's nothing to assert calls
  against — `monkeypatch` doesn't wrap your replacement in a `Mock`
  automatically.
- **Not using `raising=False` on `delenv`/`delattr` when the target may or
  may not exist**, causing tests to fail in one environment (where a
  variable happens to be set) and pass in another.
- **Leaving a stdlib patch active for an entire test when only part of it
  needs the patched behavior**, risking interference with pytest's own
  machinery for the rest of the test — this is exactly what `monkeypatch.
  context()` exists to prevent.
- **Mixing both tools inconsistently across a codebase for the same kind of
  situation**, making it harder for reviewers and new team members to
  predict which one they'll find, and harder to grep for all patches of a
  given kind.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/08-monkeypatch-vs-mock/`, build `src/config.py` with a
> `load_config()` function that reads `API_KEY`, `API_TIMEOUT` (default
> `"30"` if unset, cast to int), and the current working directory (via
> `os.getcwd()`) into a small `Config` dataclass. Write
> `tests/test_config.py` with: (1) a `monkeypatch.setenv`/`delenv` pair of
> tests covering the present and default-missing cases for both env vars;
> (2) a `monkeypatch.chdir` test using `tmp_path` (a built-in pytest
> fixture — look up what it provides) proving `load_config()` picks up the
> new working directory; (3) one test written with `mock.patch.dict
> (os.environ, {...})` doing the *same thing* as one of your `monkeypatch`
> env tests, so I can compare the two side by side and note in a comment
> which reads more clearly to me and why; (4) one `monkeypatch.context()`
> example where only half the test body has `os.getcwd` patched, with an
> assertion both inside and immediately after the `with` block proving the
> patch reverted. Do not use `mocker` (pytest-mock) anywhere in this
> exercise — that's the next lesson, and I want this one to isolate just
> `monkeypatch` vs raw `unittest.mock`.

## Quiz

1. What guarantee does `monkeypatch` give you about teardown, and how is it
   provided (mechanically) compared to `mock.patch`'s restore behavior?
2. You want to assert a patched function was called exactly twice with
   specific arguments. Is `monkeypatch.setattr` or `mock.patch` a more
   direct fit for this, and why?
3. Name two things `monkeypatch` has purpose-built methods for that
   `mock.patch` can only achieve more awkwardly.
4. What specific risk does `monkeypatch.context()` protect against that
   patching for a whole test doesn't?
5. Is there a technical reason a team *must* pick only one of `monkeypatch`
   or `mock.patch`/`mocker.patch` for their whole codebase? What's the real
   argument for standardizing on one anyway?

<details>
<summary>Answers</summary>

1. `monkeypatch` guarantees all its modifications are undone after the
   requesting test function or fixture finishes — mechanically, because it's
   implemented as a pytest fixture, and fixtures get their teardown/cleanup
   run automatically after the test (the same yield/finalizer machinery from
   Lessons 02–03). `mock.patch` achieves the equivalent restore via its own
   decorator/context-manager `__exit__`/cleanup logic, not via pytest's
   fixture system — same end guarantee, different mechanism.
2. `mock.patch` (or `mocker.patch`) is the more direct fit, because it
   auto-creates a `Mock`/`MagicMock` with built-in call-tracking and
   assertion methods (`assert_called_with`, etc.). `monkeypatch.setattr`
   would require you to manually construct and pass in a `Mock()` yourself
   to get the same call-assertion capability — technically possible, but
   `mock.patch` gives you that for free as its default behavior.
3. Environment variables (`setenv`/`delenv`, versus the more roundabout
   `patch.dict(os.environ, {...})`), and working-directory/`sys.path`
   manipulation (`chdir`, `syspath_prepend`), which have no comparably
   direct `mock.patch` equivalent at all.
4. It protects against a patch remaining active for the rest of a test's
   execution when the patched target is something pytest itself (or another
   library pytest depends on) might rely on internally — a patch scoped
   only to a `with monkeypatch.context():` block reverts immediately at the
   end of that block, rather than lingering until the whole test finishes.
5. No technical requirement — both fully support the common attribute-
   replacement case, and a suite can genuinely mix them without breaking
   anything. The real argument for standardizing is readability and
   grep-ability: a consistent house style means a reviewer or new teammate
   can predict which tool they'll find for a given situation, and can
   search the codebase for "all places we patch X kind of thing" without
   needing to check two different idioms.

</details>

## Further Reading

- pytest docs — [How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- pytest docs — [`monkeypatch` API reference](https://docs.pytest.org/en/stable/reference/reference.html#monkeypatch)

---
Previous: [07 — patch() Mechanics & Where to Patch](07-patch-mechanics-and-where-to-patch.md) · Next: [09 — pytest-mock (the mocker fixture)](09-pytest-mock-the-mocker-fixture.md)
