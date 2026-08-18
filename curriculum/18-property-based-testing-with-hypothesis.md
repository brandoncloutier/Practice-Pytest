# Lesson 18 — Property-Based Testing with Hypothesis

Phase 5: Testing Real-World Systems

## Learning Objectives

- Explain the difference between example-based testing (everything you've
  done so far) and property-based testing.
- Write a Hypothesis test using `@given` and built-in strategies.
- Explain "shrinking" and why a Hypothesis failure report is more useful
  than a fuzzer's raw crashing input.
- Identify what makes a good candidate function for property-based testing,
  and what doesn't benefit from it.

## Why This Matters in Production

Every test you've written in this curriculum so far is **example-based**:
you picked specific inputs (`apply_discount(100, 10)`) and asserted a
specific expected output. That's necessary, but it only proves correctness
for the exact examples you thought to write — and the inputs a real bug
hides behind are very often the ones nobody thought to write by hand: a
negative zero, an empty list where you assumed at least one element, a
Unicode string with combining characters, an integer right at a boundary.
Property-based testing flips the approach: instead of picking examples, you
describe a **property** that should hold for *any* valid input, and
Hypothesis generates hundreds of inputs — including deliberately
adversarial ones — trying to break that property. It's a genuinely
different testing skill, not just "parametrize but automatic."

## Concept: Example-Based vs. Property-Based

```python
# Example-based (Lesson 05's world)
@pytest.mark.parametrize("a,b,expected", [(2, 3, 5), (-1, 1, 0), (0, 0, 0)])
def test_add(a, b, expected):
    assert add(a, b) == expected

# Property-based
from hypothesis import given, strategies as st

@given(st.integers(), st.integers())
def test_add_is_commutative(a, b):
    assert add(a, b) == add(b, a)
```

The parametrized test checks specific input/output pairs you had to think
of and hand-author. The Hypothesis test checks a **property** —
commutativity — that should hold for *every* pair of integers, and lets the
library find hundreds of pairs on its own, including ones you'd never have
thought to write by hand (very large numbers, negative numbers, zero,
numbers right at `int` overflow boundaries in languages where that matters).
By default Hypothesis generates around 100 examples per `@given`-decorated
test, spending extra effort trying to find inputs that break the property,
not just sampling randomly.

## Concept: Writing a Hypothesis Test

```python
from hypothesis import given, strategies as st

def normalize_whitespace(s: str) -> str:
    return " ".join(s.split())

@given(st.text())
def test_normalize_whitespace_has_no_double_spaces(s):
    result = normalize_whitespace(s)
    assert "  " not in result

@given(st.text())
def test_normalize_whitespace_is_idempotent(s):
    once = normalize_whitespace(s)
    twice = normalize_whitespace(once)
    assert once == twice
```

Common strategies: `st.integers(min_value=..., max_value=...)`, `st.
floats(allow_nan=False, allow_infinity=False)` (worth being deliberate about
— NaN/infinity are exactly the kind of edge case Hypothesis will find if you
don't explicitly exclude them and your function isn't meant to handle them),
`st.text()`, `st.lists(st.integers(), min_size=1)`, `st.booleans()`, `st.
dates()`. **`st.builds(SomeClass, field=strategy, ...)`** constructs
instances of your own classes by drawing each constructor argument from a
strategy — useful for generating valid domain objects (a `User`, an `Order`)
rather than just primitives. For genuinely custom generation logic, `@st.
composite` lets you write a function that pulls values from several
strategies and combines them into whatever shape you need.

`@example(...)` pins a specific input to always be tested in addition to
whatever Hypothesis generates — useful for a known past regression you want
permanently covered, layered on top of the broader generated coverage:

```python
from hypothesis import given, example, strategies as st

@given(st.text())
@example("")                     # always test the empty string explicitly
@example("   ")                  # always test all-whitespace explicitly
def test_normalize_whitespace_handles_empty_input(s):
    assert normalize_whitespace(s) in ("", normalize_whitespace(s))
```

## Concept: Shrinking

When Hypothesis finds a failing input, it doesn't just report the first
random value that broke your property — it **shrinks** it, automatically
searching for the smallest, simplest failing example that still reproduces
the failure: a list of 200 elements that fails shrinks toward the smallest
sublist that still fails; a string with 40 characters shrinks toward the
shortest failing substring; a large integer shrinks toward the smallest
failing value (often toward zero). This is a meaningfully different — and
better — experience than a typical fuzzer's raw crashing input, which is
often needlessly large and full of irrelevant noise that obscures the actual
root cause. A shrunk Hypothesis failure report is usually immediately
diagnosable, often just one or two characters/elements/digits, precisely
because the library did the work of removing everything not essential to
reproducing the bug.

## Concept: What's a Good Candidate for This?

Property-based testing shines on functions with **checkable invariants** —
properties that are true regardless of the specific input, not tied to one
hand-computed expected output:

- **Round-trip properties**: `decode(encode(x)) == x` for a serializer.
- **Invariant properties**: sorting a list preserves its length and every
  element; a normalization function is idempotent (running it twice equals
  running it once).
- **Metamorphic properties**: relationships between multiple calls, like
  commutativity/associativity, or "adding an item to a cart never decreases
  the total."
- **Oracle comparison**: comparing a fast, optimized implementation against
  a slower, obviously-correct reference implementation for the same inputs.

It's a poor fit — or at least not the *first* tool to reach for — when the
correct behavior genuinely depends on external, hand-specified business
rules with no general mathematical property to check (e.g., "this specific
customer tier gets exactly this specific discount rate") — that's precisely
what Lesson 05's example-based parametrization already does well, and
forcing a "property" out of an inherently example-driven business rule
often produces a contorted, less readable test than just writing the
examples. The two approaches are complementary, not competing: many
production test suites use parametrized example-based tests for
business-rule-specific behavior and Hypothesis for functions with real
mathematical or structural invariants (parsers, serializers, calculators,
data transformations).

## Common Pitfalls

- **Writing a Hypothesis test that just re-implements the function under
  test as its own "expected" computation.** If your property is
  `assert my_function(x) == my_function(x)` in some disguised form, you've
  proven nothing — pick a genuinely independent property (round-trip,
  invariant, or a slower reference implementation) instead.
- **Not excluding known-out-of-scope inputs explicitly** (like NaN/infinity
  for a function that isn't meant to handle them), leading Hypothesis to
  "find a bug" that's actually a legitimate precondition violation — use
  `allow_nan=False`, `min_value`/`max_value`, or `.filter(...)` on the
  strategy to scope generation to valid inputs.
- **Treating a Hypothesis failure's shrunk example as the literal
  production input that will occur**, rather than as a diagnostic minimal
  reproduction of a class of inputs that share the same underlying bug —
  the value of shrinking is *diagnosis*, not necessarily realism.
- **Reaching for property-based testing on inherently example-specific
  business logic**, producing a contorted, harder-to-read test where
  straightforward `parametrize` would have communicated the requirement more
  clearly.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/18-hypothesis/`, add `hypothesis` to a
> `requirements-dev.txt` pinned to a real current version. Create
> `src/serialization.py` with `encode(data: dict) -> str` and
> `decode(s: str) -> dict` functions implementing a simple, real
> serialization format of your choosing (e.g. a basic key=value;key=value
> scheme handling string values only, with a defined escaping rule for `=`
> and `;` characters appearing inside values — document the escaping rule
> clearly in a docstring, since it's the part most likely to have a real
> bug). Then write `tests/test_serialization.py` with: (1) a Hypothesis
> round-trip test — `st.dictionaries(st.text(), st.text())` (constrain
> character sets sensibly with `st.text(alphabet=...)` if needed to keep
> the exercise tractable) — asserting `decode(encode(d)) == d` for
> generated dictionaries; (2) at least two `@example(...)` pinned cases
> covering the escaping edge cases you documented (a value containing `=`,
> a value containing `;`); (3) one deliberately introduced bug in the
> escaping logic (comment clearly marked `BUG FOR EXERCISE`) that the
> round-trip property test SHOULD catch — run it yourself first and paste
> (or describe) the shrunk failing example Hypothesis reports before fixing
> the bug, so I can see shrinking in action; (4) one small comparison test
> using `st.integers()` implementing an "oracle comparison" property: a
> simple `is_prime_naive(n)` reference function you also write (obviously
> correct but slow) compared against a `is_prime_optimized(n)` function
> (trial division up to sqrt(n) is fine) for the same generated integers.

## Quiz

1. In one or two sentences, what's the core difference in testing
   philosophy between `@pytest.mark.parametrize` and `@given`?
2. Give an example of a "round-trip property" different from the one in
   this lesson, for any function you can think of.
3. What does Hypothesis's "shrinking" actually do when a test fails, and
   why is a shrunk failing example generally more useful for debugging than
   the first random input that happened to trigger the failure?
4. You write `@given(st.floats())` for a function that's explicitly
   documented to never receive NaN or infinity in production. What's likely
   to happen, and what's the fix?
5. A teammate wants to Hypothesis-test a function whose correct output is a
   specific, hand-specified discount percentage per named customer tier
   (`"gold"` → 15%, `"silver"` → 10%, etc.), with no general mathematical
   relationship between tiers. Is this a good property-based testing
   candidate? What would you suggest instead, and why?

<details>
<summary>Answers</summary>

1. `parametrize` checks specific, hand-chosen input/output examples you
   thought of in advance. `@given` checks that a general property holds
   across a wide, automatically-generated (and adversarially-searched)
   range of inputs, without you needing to enumerate the inputs yourself —
   trading example-authoring effort for the ability to find inputs you
   wouldn't have thought to write by hand.
2. Any function with a real inverse: e.g., a URL-encoding function and its
   decoder (`url_decode(url_encode(s)) == s`), a compression function and
   its decompressor, a `to_json`/`from_json` pair for a data class, or a
   database "insert then fetch" pair (`fetch(insert(record)) == record`).
3. Shrinking is Hypothesis automatically searching for the smallest/
   simplest input that still reproduces a discovered failure — reducing
   list length, string length, or numeric magnitude step by step while
   re-checking the failure still occurs. It's more useful than the raw
   first failing input because that first input is often large, noisy, and
   full of irrelevant detail; the shrunk version isolates just what's
   actually necessary to trigger the bug, making the root cause far easier
   to spot.
4. Hypothesis will very likely generate NaN and/or infinity (they're valid
   `float` values) and "discover" a failure, because the function was never
   designed to handle them — this isn't a real bug in the sense of a
   violated business requirement, but it will look like a Hypothesis
   failure. The fix is scoping the strategy to the function's actual valid
   input domain, e.g. `st.floats(allow_nan=False, allow_infinity=False)`,
   so Hypothesis only generates inputs the function is actually meant to
   handle.
5. Not a good fit as the primary tool — there's no general mathematical or
   structural property connecting the tiers' discount rates; it's a
   hand-specified business rule table. `pytest.mark.parametrize` (Lesson
   05) with explicit `(tier, expected_discount)` pairs and readable `id=`
   values communicates the actual requirement far more directly, and is
   easier for a future reader to verify against the real business rule
   document than a contorted "property" would be. Property-based testing
   would be worth layering in only for something like "the returned
   discount is always between 0 and 100" as a sanity-check invariant, not
   as a replacement for the tier-specific examples.

</details>

## Further Reading

- Hypothesis docs — [Quick start guide](https://hypothesis.readthedocs.io/en/latest/quickstart.html)
- Hypothesis docs — [What you can generate and how (strategies reference)](https://hypothesis.readthedocs.io/en/latest/reference/strategies.html)
- Hypothesis docs — [Details and advanced features (shrinking, `@example`, `@settings`)](https://hypothesis.readthedocs.io/en/latest/details.html)

---
Previous: [17 — Testing Async Code](17-testing-async-code.md) · Next: [19 — CI/CD Integration & Tooling](19-ci-cd-integration-and-tooling.md)
