# Lesson 05 — Parametrization Mastery

Phase 2: Fixtures & Parametrization Mastery

## Learning Objectives

- Use `pytest.mark.parametrize` beyond simple value lists: multiple
  parameters, stacked decorators, and `pytest.param` with custom IDs and
  marks.
- Parametrize a **fixture** (not just a test function) using
  `@pytest.fixture(params=...)`, and explain when that's the better tool.
- Use `indirect=True` to route parametrize values through a fixture instead
  of straight into the test.
- Read parametrized test IDs in `pytest -v` output and know how to make them
  more readable.

## Why This Matters in Production

You already use `pytest.mark.parametrize` for the common case: one function,
a list of `(input, expected)` tuples. Production suites push further —
testing a function against a matrix of two or three independent dimensions,
sharing the *same* parametrization across many test functions via a fixture,
or needing every test that touches a resource (e.g. "every supported database
backend") to run once per variant without rewriting each test body. This
lesson is about not reinventing those wheels with manual `for` loops or
copy-pasted test functions, both of which are common (and both of which
actively fight pytest's reporting — a `for` loop inside one test reports as a
single pass/fail instead of N independently-reportable results).

## Concept: Beyond the Basics

You know this shape:

```python
@pytest.mark.parametrize("value,expected", [
    (1, 1),
    (-1, 1),
    (0, 0),
])
def test_abs(value, expected):
    assert abs(value) == expected
```

Two things worth formalizing:

**Stacking `parametrize` multiplies combinations.** Two stacked decorators
with 3 and 2 values each produce 6 test runs — every combination:

```python
@pytest.mark.parametrize("discount", [0, 10, 25])
@pytest.mark.parametrize("currency", ["USD", "EUR"])
def test_price_formatting(currency, discount):
    ...
# runs 6 times: (USD,0) (USD,10) (USD,25) (EUR,0) (EUR,10) (EUR,25)
```

This is a real Cartesian product tool for testing genuinely independent
dimensions — use it deliberately, not by accident. Six related-but-distinct
parametrize sets stacked together can produce hundreds of test IDs that
"pass" in aggregate while hiding which specific combination actually matters.

**`pytest.param` lets you attach IDs and marks per case:**

```python
@pytest.mark.parametrize("payload,expected_status", [
    pytest.param({"name": "ok"}, 201, id="valid-payload"),
    pytest.param({}, 422, id="missing-name"),
    pytest.param({"name": "x" * 300}, 422, id="name-too-long",
                 marks=pytest.mark.xfail(reason="known bug JIRA-1821")),
])
def test_create_user(payload, expected_status, api_client):
    resp = api_client.post("/users", json=payload)
    assert resp.status_code == expected_status
```

Without explicit `id=`, pytest auto-generates IDs from the values (often
ugly for dicts/objects — you'll see `payload0`, `payload1`). Explicit IDs are
worth the extra typing the moment a teammate needs to run
`pytest -k missing-name` to reproduce one failing case, or reads a CI failure
list and needs to know *which* case failed without opening the file.

## Concept: Parametrizing a Fixture

Sometimes what varies isn't an input value passed straight to the test body —
it's the whole *object under test*. `@pytest.fixture(params=...)` handles
this, and every test that requests the fixture (by name, transparently) runs
once per param value:

```python
@pytest.fixture(params=["sqlite", "postgres"])
def db_backend(request):
    if request.param == "sqlite":
        return connect_sqlite_memory()
    return connect_postgres_test_container()

def test_insert_and_read(db_backend):
    db_backend.insert("users", {"name": "Ada"})
    assert db_backend.read("users")[0]["name"] == "Ada"

def test_unique_constraint(db_backend):
    db_backend.insert("users", {"id": 1})
    with pytest.raises(IntegrityError):
        db_backend.insert("users", {"id": 1})
```

Both tests here run twice each (once per backend) — **without either test
function mentioning parametrization at all**. This is the key difference from
`@pytest.mark.parametrize`: that decorator parametrizes *one test function*;
a parametrized fixture parametrizes *every test that uses it*, which is
exactly what you want when "run against every supported backend" is a
cross-cutting concern for a whole test module, not a property of one test.

## Concept: `indirect=True`

Normally, `parametrize` values go straight into the test function as
arguments. `indirect=True` routes them through a fixture of the same name
first — the fixture receives the value via `request.param` and can transform
it before the test sees it:

```python
@pytest.fixture
def user(request):
    # request.param is whatever parametrize passed in
    role = request.param
    return User(name="Test", role=role, permissions=PERMISSIONS[role])

@pytest.mark.parametrize("user", ["admin", "editor", "viewer"], indirect=True)
def test_permissions_assigned(user):
    assert user.permissions  # `user` here is a fully built User object,
                              # not the string "admin"/"editor"/"viewer"
```

This is the right tool when the raw parametrize value needs setup/lookup
logic before the test can use it directly — you get parametrization *and*
fixture-style construction in one mechanism, instead of duplicating that
construction logic inside every test function that needs a role-based user.

## Common Pitfalls

- **Using a `for` loop inside a test body instead of `parametrize`.** It
  compiles and "works," but pytest reports the whole loop as a single
  pass/fail. One failing case among ten stops the loop and hides the other
  nine results; with `parametrize`, all ten run and report independently,
  every time, and `-k` can target exactly one.
- **Ugly auto-generated IDs making CI failures hard to act on.** If your
  `-v` output shows `test_create_user[payload2-422]`, that's a debugging
  tax on every future failure. Add `id=` (or the `ids=` list/callable
  argument) the moment parameter values aren't self-descriptive primitives.
- **Confusing "parametrize the test" with "parametrize the fixture."** If
  you find yourself writing the *same* `@pytest.mark.parametrize(...)`
  decorator above five different test functions in a file, that's usually a
  sign the parametrization belongs on a shared fixture instead — DRY applies
  to test setup just as much as production code.
- **Stacking parametrize decorators without checking the combinatorial
  size.** Three stacked decorators with 4/3/3 values each produce 36 test
  runs. That's sometimes exactly right (real matrix testing) and sometimes a
  sign you parametrized something that should have been three separate,
  more targeted tests instead.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/05-parametrization/`, write a `src/pricing.py` module with a
> function `apply_discount(price: float, percent: float, currency: str) ->
> float` that rounds to 2 decimal places and raises `ValueError` for a
> negative price or a percent outside 0–100. Then build
> `tests/test_pricing.py` with: (1) a `parametrize` test covering at least 5
> valid `(price, percent, currency, expected)` cases with explicit
> human-readable `id=` values via `pytest.param`; (2) a *separate*
> `parametrize` test for the invalid-input cases that expects `ValueError`,
> also with explicit IDs; (3) two stacked `parametrize` decorators (small —
> 3x2 at most) proving you understand combination multiplication, with a
> comment stating how many total test runs you expect before I run it; (4) a
> `params=`-parametrized fixture called `rounding_mode` (values like
> `"half_up"` and `"half_even"`) used by at least two different test
> functions, to demonstrate the difference from function-level
> `parametrize`; (5) one `indirect=True` example where a `parametrize` value
> like `"vip"` / `"standard"` routes through a fixture that returns a
> `Customer` object with a `discount_multiplier` attribute, rather than the
> raw string. Have me run `pytest -v` and predict the full list of test IDs
> before I look at the actual output.

## Quiz

1. What's structurally different about how pytest *reports* results between
   a `for` loop inside a test body and an equivalent `@pytest.mark.
   parametrize` list?
2. You stack `@pytest.mark.parametrize("a", [1,2])` above
   `@pytest.mark.parametrize("b", ["x","y","z"])` on one test function. How
   many total test runs does this produce, and why?
3. What's the core difference between `@pytest.mark.parametrize` on a test
   function and `@pytest.fixture(params=[...])`, in terms of *what* gets
   parametrized?
4. When would you reach for `indirect=True` instead of just parametrizing
   the test function directly with the final value you actually want to
   test with?
5. Why does an auto-generated test ID like `test_create_user[payload2-422]`
   cause real friction in a CI environment, and what's the fix?

<details>
<summary>Answers</summary>

1. A `for` loop is invisible to pytest's reporting — the whole test function
   is one collected item, and it's one pass or one fail overall (the loop
   stops at the first failing iteration, hiding results for any iterations
   after it). `@pytest.mark.parametrize` makes pytest collect and report each
   parameter set as its own independent test item, so all of them run to
   completion every time, each with its own pass/fail outcome and its own ID
   you can target individually.
2. 6 total runs (2 × 3) — stacking `parametrize` decorators produces the full
   Cartesian product of all the parameter sets, not the sum. Every value of
   `a` runs against every value of `b`.
3. `@pytest.mark.parametrize` on a test function parametrizes that *one*
   test function — the values are scoped to it alone. `@pytest.fixture
   (params=[...])` parametrizes the *fixture*, which means every test that
   requests that fixture (by name) automatically runs once per param value,
   without any of those test functions needing their own `parametrize`
   decorator.
4. When the raw parametrize value needs construction/lookup logic before the
   test can use it meaningfully — e.g., a short string like `"admin"` needs
   to become a fully-built `User` object with role-specific permissions.
   `indirect=True` routes the raw value through a fixture (via
   `request.param`) so that construction logic lives in one fixture instead
   of being duplicated inside every test that needs a similarly-built object.
5. Because it forces a debugging reader (someone triaging a red CI run) to
   go open the test file and count parameter list entries to figure out
   which case index 2 refers to, instead of being able to tell from the
   failure output alone. The fix is supplying explicit, human-readable IDs
   via `pytest.param(..., id="...")` or the `ids=` argument to
   `parametrize`.

</details>

## Further Reading

- pytest docs — [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- pytest docs — [`pytest.param` API reference](https://docs.pytest.org/en/stable/reference/reference.html#pytest-param)

---
Previous: [04 — Fixture Composition, Factories & conftest.py](04-fixture-composition-and-conftest.md) · Next: [06 — unittest.mock Deep Dive](06-unittest-mock-deep-dive.md)
