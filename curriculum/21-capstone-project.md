# Lesson 21 — Capstone Project

Capstone

## Goal

Design and build a test suite for a small, production-shaped service,
applying every phase of this curriculum deliberately — not just
mechanically checking off techniques, but making and *defending* real
design decisions the way you would in a code review at work. This lesson
has no quiz; the project itself, and the design write-up at the end, is the
assessment.

## The System to Build

Build a small **order/inventory service** — small enough to finish in a
reasonable number of sessions, but with enough real seams (an external
payment API, a database, business rules with edge cases, some async
work) to force genuine decisions from every phase. Suggested shape (adapt
freely — the point is the seams, not this exact domain):

- **`InventoryRepository`** — persistence layer (SQL database) tracking
  item stock levels.
- **`PricingEngine`** — internal, pure business logic: computes order
  totals, applies tier-based discounts, handles tax — no external calls.
- **`PaymentGateway`** — a thin client wrapping a real external HTTP
  payment API (real shape, fake/sandbox target for testing).
- **`NotificationService`** — sends order-confirmation emails/webhooks,
  another external boundary.
- **`OrderService`** — orchestrates all of the above: validates stock via
  `InventoryRepository`, computes the total via `PricingEngine`, charges via
  `PaymentGateway`, decrements stock, and notifies via
  `NotificationService`, with real failure-handling requirements (what
  happens if payment succeeds but stock decrement fails? what happens if
  notification fails after a successful charge? — these are genuine design
  questions, not just testing questions, and your test suite should make
  the intended behavior explicit).
- Optionally, an **async background worker** that processes a queue of
  pending notifications, to pull in Lesson 17.

You are welcome (encouraged, even) to have Claude Code scaffold the
*production* code for this service quickly — the learning target of this
capstone is the test suite and the testing decisions behind it, not
hand-writing the business logic from scratch. Do write the tests yourself,
using Claude Code as a reviewer and sounding board rather than the author,
consistent with how this curriculum has framed the exercises throughout.

## Requirements Checklist

Work through this list; it maps directly back to the curriculum phases.

**Fixtures (Phase 2)**
- [ ] At least one `session`-scoped fixture for something genuinely
      expensive and safely shareable (e.g. a `testcontainers` database
      engine), and at least one `function`-scoped fixture layered on top for
      per-test isolation (Lesson 03's `db_engine`/`db_session` split).
- [ ] At least one factory-as-fixture (Lesson 04) for generating test
      orders/items with sensible defaults and per-test overrides.
- [ ] A `conftest.py` structure with at least one meaningful override
      between a root-level and a more specific subdirectory (Lesson 04).

**Parametrization (Phase 2)**
- [ ] A parametrized test covering at least 4 distinct pricing/discount
      scenarios with explicit, readable `id=` values (Lesson 05).
- [ ] At least one parametrized *fixture* (not just a parametrized test)
      where it's the more appropriate tool (Lesson 05).

**Mocking (Phase 3)**
- [ ] At least one test where you deliberately chose a **stub**, one where
      you chose a **fake**, one where you chose a **spy**, and one where you
      chose a **mock** (behavior verification) — each with a one-line
      comment justifying the choice per Lesson 10's decision process. This
      is the single most important checklist item in this capstone.
- [ ] At least one test demonstrating correct "patch where it's used"
      target resolution (Lesson 07) for the `PaymentGateway` or
      `NotificationService` client.
- [ ] Deliberately avoid mocking `PricingEngine` in any `OrderService` test
      — use the real thing, since it's internal logic (this directly
      exercises the Lesson 10 anti-pattern warning).

**Production Test Design (Phase 4)**
- [ ] At least one `pytest.raises` test with `match=` and exception-object
      inspection for a real failure path (e.g., insufficient stock).
- [ ] At least one `caplog` test verifying a specific log line is emitted
      on a failure path (e.g., payment succeeded but stock decrement
      failed — the kind of case that should be loud in production logs).
- [ ] Custom markers (`slow`, `integration`) registered and applied
      correctly, with at least one `xfail(strict=True)` if you have a
      genuinely known, tracked bug, or a `skipif` with a real reason if
      relevant.
- [ ] Test files organized into `tests/unit/` and `tests/integration/`
      using this curriculum's concrete criterion (Lesson 13) for which is
      which — write a one-sentence justification per directory in a
      `tests/README.md` you author yourself.
- [ ] Run `pytest --cov=src --cov-branch --cov-report=term-missing` and
      review the output critically — for any file below 100% branch
      coverage, explicitly decide (and note in a comment) whether that gap
      is acceptable or worth closing, rather than blindly chasing 100%.

**Real-World Systems (Phase 5)**
- [ ] `PaymentGateway` tests use `responses` (or `respx`, matching your
      HTTP client choice) at the transport layer, including at least one
      simulated network failure (Lesson 15).
- [ ] `InventoryRepository` tests use the transactional-rollback pattern
      against a real database (SQLite is acceptable here if you note the
      dialect-accuracy tradeoff from Lesson 16; `testcontainers` is the
      stronger choice if you have Docker available).
- [ ] If you built the async worker: at least one test using `AsyncMock`
      correctly, including an `assert_awaited_once_with` assertion
      (Lesson 17).
- [ ] At least one Hypothesis property-based test against `PricingEngine`
      — pick a genuine invariant (e.g., "total is never negative,"
      "discount never increases total") rather than forcing one onto
      inherently example-specific logic (Lesson 18).

**Pipeline Practices (Phase 6)**
- [ ] A `pyproject.toml` with `--strict-markers`, `--strict-config`,
      `xfail_strict = true`, and registered markers (Lesson 19).
- [ ] Confirm the suite passes cleanly under `pytest -n auto` (install
      `pytest-xdist`) — if anything fails or behaves differently under
      parallel execution, diagnose and fix the hidden state coupling before
      considering this item done (Lessons 13, 19, 20).
- [ ] Write, in your own words, the staged CI pipeline you'd actually set
      up for this service (fast-checks / full-suite / integration), as a
      short markdown doc — you don't need a real CI vendor config, just the
      `-m` expressions and the reasoning for what runs where and how often.

## The Design Write-Up

When the checklist is done, write a short (roughly 1–2 page) design
document — for yourself, and to hand to Claude Code for a genuinely
critical review (ask explicitly for pushback, not validation). Cover:

1. **Test double decisions**: for each external boundary in the system
   (`PaymentGateway`, `NotificationService`, the database), what double(s)
   did you use where, and why? Where did you deliberately choose *not* to
   double something?
2. **The one test you're least confident in**: which test in your suite do
   you think is most likely to be brittle, redundant, or not actually
   proving what it claims? Why do you suspect that, and what would you do
   about it given more time?
3. **What you'd do differently for a 10x larger version of this service**:
   which of your current choices (fixture scopes, database strategy, how
   much you rely on SQLite vs. a real container) would need to change, and
   why?
4. **One thing this curriculum didn't cover that you needed to figure out
   yourself** — even a small thing. Production testing always has edges a
   curriculum can't fully anticipate; noticing and naming one is itself a
   sign you've internalized the material rather than just followed
   instructions.

## How to Use Claude Code Here

This is the one lesson in the curriculum where handing Claude Code more of
the *production* code (not just scaffolding) is appropriate — the capstone
is testing your testing judgment, not your ability to hand-write a payment
gateway client from scratch. Suggested flow:

1. Ask Claude Code to scaffold the production classes/modules listed above,
   reasonably realistic but intentionally including a couple of genuine
   edge cases and at least one subtle bug for you to catch via testing
   (tell it explicitly: "include 1-2 realistic bugs I should find by
   writing thorough tests, don't tell me where").
2. Write the test suite yourself against the checklist above, lesson by
   lesson, referring back to specific curriculum files as needed.
3. When you believe you're done, ask Claude Code to review your test suite
   *without* looking at the production code's bugs directly — ask it to
   find gaps in your test design (missing edge cases, wrong double choices,
   assertion roulette, etc.) referencing this curriculum's vocabulary.
4. Separately, ask it whether your tests actually caught the deliberately
   planted bugs — if they didn't, that's the most valuable single data
   point this whole capstone can give you about your own blind spots.
5. Write the design document. Ask Claude Code to push back on it —
   specifically prompt for disagreement, not agreement.

## When You're Done

Check off Lesson 21 in [`PROGRESS.md`](../PROGRESS.md). You've now gone
through fixture lifecycle and composition, the full mocking taxonomy and
mechanics, production test design and failure-path testing, HTTP/database/
async/property-based testing, and pipeline practices — applied together, on
purpose, on something with real seams. That combination — not any single
technique — is what "solid foundation in production pytest" actually means.

---
Previous: [20 — Flaky Tests & Anti-Patterns](20-flaky-tests-and-anti-patterns.md) · Back to: [Roadmap](00-roadmap.md)
