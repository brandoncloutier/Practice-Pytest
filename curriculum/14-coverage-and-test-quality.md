# Lesson 14 — Coverage & Test Quality

Phase 4: Production Test Design

## Learning Objectives

- Run and interpret `pytest-cov` output, including branch coverage.
- Explain precisely why 100% line coverage does not mean "well tested," with
  a concrete counterexample.
- Explain what mutation testing measures that line/branch coverage cannot,
  and run a basic `mutmut` session.
- Set a coverage gate in CI deliberately, understanding what it does and
  doesn't guarantee.

## Why This Matters in Production

Coverage percentage is the most commonly Goodharted metric in testing:
the moment it becomes a target ("we require 90% coverage to merge"), people
write tests that execute lines without meaningfully checking behavior, just
to move the number. This lesson is about using coverage as a **diagnostic
tool** (finding code nobody tests at all) rather than a **quality proxy**
(assuming tested-line-count correlates with confidence), and introduces
mutation testing as the sharper, if more expensive, alternative for
answering "how good are these tests, actually."

## Concept: Running `pytest-cov`

```bash
pip install pytest-cov
pytest --cov=src --cov-report=term-missing
```

```
Name                 Stmts   Miss  Cover   Missing
--------------------------------------------------
src/pricing.py           24      3    88%   17-19
src/checkout.py          40      0   100%
--------------------------------------------------
TOTAL                    64      3    95%
```

`--cov-report=term-missing` shows exactly which line numbers were never
executed — the single most useful view for "what did we forget to test at
all." `--cov-report=html` generates a browsable report highlighting
uncovered lines directly in the source, often faster to scan for a whole
module than a terminal line-number list.

**Branch coverage** (`--cov-branch`) is stricter than line coverage: line
coverage only checks that a line *executed*, not that every branch through
it did. Classic gap:

```python
def apply_discount(price, is_member):
    if is_member:
        price *= 0.9
    return price
```

A single test calling `apply_discount(100, True)` gives 100% *line*
coverage — every line executed — while never exercising the `is_member=False`
path at all. `--cov-branch` reports this as a missed branch, because it
tracks whether each conditional's *both* outcomes were taken, not just
whether the `if` line itself ran once.

## Concept: Why 100% Coverage Doesn't Mean "Well Tested"

Coverage measures **execution**, not **verification**. A test that executes
a line but doesn't assert anything meaningful about its result still counts
as covering that line:

```python
def calculate_shipping(weight, distance):
    if weight <= 0:
        raise ValueError("weight must be positive")
    return round(weight * distance * 0.15, 2)

def test_calculate_shipping():          # 100% line coverage, useless test
    calculate_shipping(5, 100)          # no assertion at all!
```

This test achieves full coverage of `calculate_shipping` and proves
*nothing* — it doesn't even check the function doesn't crash with a
different, wrong answer, because there's no assertion comparing the actual
result to an expected one. Coverage tools cannot detect a missing or weak
assertion; they only track which lines the interpreter executed. This is
the core reason coverage percentage, alone, is a poor proxy for test
quality — it answers "did we run this code" not "did we verify this code is
correct."

A subtler version of the same gap: a test with a correct assertion, but only
against one input, when the function has meaningfully different behavior
across an input range (Lesson 05's parametrization and Lesson 18's
property-based testing both exist partly to close this specific gap).

## Concept: Mutation Testing

If coverage can't tell you whether your assertions are meaningful, what
can? **Mutation testing** deliberately introduces small, syntactic bugs
("mutants") into your source code — flipping a comparison operator, changing
a `+` to a `-`, negating a boolean — then reruns your test suite against
each mutant. If your tests still pass despite the injected bug, that mutant
"survived," which tells you concretely: **your tests would not have caught
this specific class of real bug.** A mutant that gets "killed" (a test
failed because of it) is evidence your tests actually verify something
meaningful at that location, not just that they execute it.

```bash
pip install mutmut
mutmut run          # mutates src/, reruns pytest against each mutant
mutmut browse        # interactively review surviving mutants
```

Mutation testing is significantly more expensive than plain coverage (it
reruns your whole suite once per mutant, potentially hundreds of times for a
non-trivial module), so it's not something you run on every commit — it's a
periodic, deliberate audit tool, often run on a schedule or targeted at a
specific critical module rather than a whole codebase on every PR. Its
value: a high mutation-kill-score on a module is meaningfully stronger
evidence of test quality than a high line-coverage percentage on the same
module, precisely because it measures whether your assertions would catch
real, small, plausible bugs — not just whether the lines ran.

## Concept: Setting a Coverage Gate Thoughtfully

A common CI pattern:

```bash
pytest --cov=src --cov-report=term-missing --cov-fail-under=85
```

This is legitimate and useful as a **regression floor** — catching an
obviously untested new module before merge — but it's worth being explicit
with your team about what it does and doesn't guarantee: it prevents
coverage from *dropping*, and flags large untested blocks; it says nothing
about whether the tests that do exist are any good, per everything above.
Teams that treat a coverage threshold as the definition of "done" testing
tend to accumulate exactly the assertion-free, box-checking tests shown
above. Teams that treat it as a floor — supplemented by code review
attention to what's actually being asserted, and periodic mutation testing
on critical modules — get more out of the same metric without over-trusting
it.

## Common Pitfalls

- **Chasing 100% coverage on code that doesn't warrant it.** Trivial
  `__repr__` methods, defensive `else: raise AssertionError("unreachable")`
  branches, and generated code often aren't worth the engineering time to
  cover — `# pragma: no cover` exists for a reason; use it deliberately and
  visibly, not silently.
- **Writing tests specifically to move the coverage number**, without
  meaningful assertions — the exact failure mode this lesson's
  `calculate_shipping` example demonstrates.
- **Only checking line coverage when branch coverage would reveal a real
  gap.** Any function with conditionals deserves `--cov-branch` at least
  periodically, not just line coverage.
- **Running mutation testing on every commit and being surprised it's
  slow.** It's an audit tool, not a CI gate for every PR — run it on a
  schedule, or scoped to specific critical modules, and treat surviving
  mutants as a backlog to triage, not a blocking gate.
- **Treating `--cov-fail-under` as proof of quality** rather than as a floor
  against obvious regressions — see the discussion above.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/14-coverage-and-quality/`, create `src/shipping.py` with
> the `calculate_shipping(weight, distance)` function shown in this lesson
> (validate weight > 0, compute a rounded cost) plus one additional function
> `apply_bulk_discount(cost, item_count)` that has a real conditional branch
> (e.g., 10% off if `item_count >= 10`). First write
> `tests/test_shipping_weak.py`: tests that call both functions but include
> at least one test with NO assertion at all (reproducing the lesson's
> "100% coverage, useless test" example on purpose) and at least one test
> that only covers the `item_count >= 10` branch, never the else branch.
> Run `pytest --cov=src --cov-report=term-missing` and
> `pytest --cov=src --cov-branch --cov-report=term-missing` for me to
> compare, and note in a comment what branch coverage catches that line
> coverage misses here. Then write a SEPARATE, properly assertion-complete
> `tests/test_shipping_strong.py` covering both branches of
> `apply_bulk_discount` and the validation error path of
> `calculate_shipping`, with real assertions throughout. Add a
> `requirements-dev.txt` with `pytest-cov` and `mutmut` pinned to real
> current versions, and leave a comment with the exact `mutmut run` command
> I should try myself against `test_shipping_strong.py` vs
> `test_shipping_weak.py`, predicting (before I run it) which one should
> have a higher mutation kill score and why.

## Quiz

1. A module shows 100% line coverage. What can you conclude about its test
   quality, and what can you NOT conclude?
2. Give a concrete example (can reuse the lesson's shape, different
   specifics) of a function where line coverage hits 100% but branch
   coverage reveals a real gap.
3. What does a "surviving mutant" tell you, specifically, that a coverage
   report cannot?
4. Why is mutation testing typically run on a schedule or against specific
   modules, rather than as a gate on every pull request?
5. Your team currently requires 85% coverage to merge. What's a
   legitimate use of that gate, and what's a way teams misuse it that this
   lesson warns against?

<details>
<summary>Answers</summary>

1. You can conclude every line in the module executed at least once during
   the test run — nothing more. You cannot conclude the tests contain
   correct or even present assertions, that all logical branches were
   exercised (that's what branch coverage adds), or that the tests would
   catch a real bug introduced later — coverage measures execution, not
   verification.
2. Any function with an `if/else` (or equivalent) where only one branch is
   exercised by the test suite: e.g., a function that applies a late fee
   only if a payment is overdue — a single test with an on-time payment
   gives 100% line coverage of the whole function (every line ran) while
   never executing the late-fee branch at all; `--cov-branch` would flag
   the untaken branch specifically.
3. It tells you that a specific, small, realistic code change (the mutation
   — e.g., a flipped comparison operator or a changed constant) at that
   exact location would NOT have been caught by your current test suite —
   direct evidence of a gap in what your assertions actually verify, not
   just which lines execute. A coverage report cannot distinguish "this
   line ran and was correctly verified" from "this line ran and nothing
   checked whether it did the right thing."
4. Because it reruns the entire test suite once per generated mutant
   (potentially hundreds of reruns for a non-trivial module), making it
   dramatically more expensive than a normal test run or a coverage pass —
   running it on every PR would make CI prohibitively slow. It's better
   suited as a periodic audit (scheduled, or scoped to specific
   high-value/high-risk modules) whose findings become a backlog to triage.
5. Legitimate use: a regression floor that catches an obviously
   under-tested new module before it merges, prompting a reviewer to ask
   "why is this at 40%?" Misuse this lesson warns against: treating the
   85% threshold as the definition of "sufficiently tested," which
   incentivizes writing assertion-free or trivially-covering tests purely
   to clear the number, rather than genuinely verifying behavior.

</details>

## Further Reading

- pytest-cov docs — [PyPI project page](https://pypi.org/project/pytest-cov/)
- coverage.py docs — [Branch coverage](https://coverage.readthedocs.io/en/latest/branch.html)
- mutmut docs — [Getting started](https://mutmut.readthedocs.io/en/latest/)

---
Previous: [13 — Test Organization at Scale](13-test-organization-at-scale.md) · Next: [15 — Testing HTTP & External Services](15-testing-http-and-external-services.md)
