# Lesson 16 — Testing Databases & Persistence

Phase 5: Testing Real-World Systems

## Learning Objectives

- Implement the transactional-rollback fixture pattern for fast, isolated
  database tests.
- Use `factory_boy` to generate realistic test data instead of hand-writing
  every field of every test object.
- Explain the tradeoffs between an in-memory/lightweight database (e.g.
  SQLite) and a real containerized database (via `testcontainers`) for
  tests, and when each is the right call.
- Recognize when a fake in-memory repository (Lesson 10) is preferable to
  hitting any real database at all.

## Why This Matters in Production

Database tests are where a lot of the earlier lessons converge under real
pressure: fixture scope (Lesson 03) determines whether you reconnect to a
database once or two thousand times; the factory-as-fixture pattern
(Lesson 04) is exactly how you avoid hand-writing every test row; and the
fake-vs-real-boundary decision (Lesson 10) is never more consequential than
here, because "just mock the database" is both extremely tempting and
usually wrong once the logic under test involves real query behavior,
constraints, or transactions.

## Concept: The Transactional Rollback Pattern

You saw the shape of this in Lesson 03; here's the full reasoning. The goal:
every test gets a database that looks freshly seeded (or empty), without the
cost of tearing down and recreating the whole database (or even truncating
every table) between each of potentially thousands of tests.

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("postgresql://localhost/app_test")
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()   # undoes everything this test did, instantly
    connection.close()

def test_creating_order_persists_it(db_session):
    order = Order(item="Widget", quantity=3)
    db_session.add(order)
    db_session.commit()

    fetched = db_session.query(Order).filter_by(item="Widget").one()
    assert fetched.quantity == 3
```

The trick: the test's `session.commit()` commits *within* an outer
transaction that the fixture already opened and never actually commits at
the database level — `transaction.rollback()` in teardown discards
everything, regardless of how many times the test itself called `.commit()`
on its ORM session. This gives you full isolation (nothing a test does is
visible to any other test) at roughly the cost of one connection checkout
per test, not a full schema teardown/recreate — the same wide-connection/
narrow-transaction split from Lesson 03's `db_engine`/`db_session` example,
now with the actual mechanism explained.

## Concept: Generating Test Data with `factory_boy`

Hand-writing every field of every test row gets unsustainable fast,
especially as models grow required fields and constraints. `factory_boy`
gives you declarative factories, analogous to the make_user pattern from
Lesson 04 but with more built-in machinery for realistic, varied data:

```python
import factory
from myapp.models import User

class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: n)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Faker("name")
    is_active = True

def test_inactive_users_excluded_from_digest(db_session):
    UserFactory._meta.sqlalchemy_session = db_session
    active = UserFactory.create_batch(3, is_active=True)
    inactive = UserFactory.create(is_active=False)

    recipients = build_digest_recipients(db_session)

    assert len(recipients) == 3
    assert inactive.email not in [r.email for r in recipients]
```

`factory.Sequence` guarantees unique values across calls (critical for
fields with unique constraints, like `email`), and `factory.Faker`
integrates the `Faker` library for realistic-looking random data (names,
addresses, etc.) without you hand-authoring it. `create_batch(3, ...)`
generates several at once, letting a test express "three active users and
one inactive one" in two lines instead of manually constructing and
inserting four full objects, which both reduces noise and makes the
*meaningful* difference between rows (the `is_active` flag, here) stand out
clearly to a reader.

## Concept: In-Memory/Lightweight DB vs. a Real Containerized DB

Two common choices for what "the database" actually is during tests:

**SQLite in-memory** — extremely fast, zero external dependency, but not
the same database engine as production if you run Postgres/MySQL in
production. Differences in SQL dialect, constraint enforcement, JSON column
behavior, and concurrency semantics can all mean a test passes against
SQLite but would fail (or behave differently) against the real production
engine.

**A real database via `testcontainers`** — spins up an actual, disposable
Postgres/MySQL/etc. instance in a Docker container for the test run,
guaranteeing dialect-accurate behavior at the cost of needing Docker
available and noticeably slower startup (seconds, not milliseconds):

```python
from testcontainers.postgres import PostgresContainer
import sqlalchemy

@pytest.fixture(scope="session")
def db_engine():
    with PostgresContainer("postgres:16") as postgres:
        engine = sqlalchemy.create_engine(postgres.get_connection_url())
        yield engine
```

**A practical default for production codebases:** use `testcontainers`
(or an equivalent real-database setup) for the actual CI/integration test
suite, since it's the only option that gives you dialect-accurate
guarantees — SQLite-in-memory is a legitimate choice **only** when the team
has explicitly verified (or constrained itself to) SQL that behaves
identically across both engines, which is a real, ongoing discipline, not a
one-time check. If you inherit a codebase using SQLite for speed and you're
not sure this discipline has been maintained, that's worth raising, not
assuming.

## Concept: When a Fake Beats Any Real Database

Revisiting Lesson 10's taxonomy directly: if the code under test's logic
genuinely doesn't depend on real SQL behavior — no constraint enforcement,
no complex queries, no transaction semantics being tested — a **fake**
in-memory repository (a plain Python dict-backed class implementing the same
interface as the real repository) can be the right call, faster than even
SQLite and with zero setup:

```python
class FakeOrderRepository:
    def __init__(self):
        self._orders = {}
        self._next_id = 1

    def save(self, order):
        order.id = self._next_id
        self._orders[order.id] = order
        self._next_id += 1
        return order

    def get(self, order_id):
        return self._orders.get(order_id)

def test_order_total_calculation():
    repo = FakeOrderRepository()
    order = repo.save(Order(items=[Item(price=10), Item(price=5)]))
    assert calculate_order_total(repo, order.id) == 15
```

The tradeoff, per Lesson 10: this only stays trustworthy if the fake's
behavior doesn't silently drift from the real repository's actual contract
(e.g., if the real one enforces a max-items-per-order constraint the fake
doesn't). Worth pairing with at least one real integration test exercising
the same interface against the actual database, to keep the fake honest.

## Common Pitfalls

- **Reflexively mocking the database layer entirely (a bare `Mock()`
  standing in for a repository) for logic that's really about SQL/query
  correctness.** That's the "mock everything" anti-pattern from Lesson 10 —
  it proves your code calls a method, not that the query does the right
  thing.
- **Not using the transactional-rollback pattern and instead truncating
  tables (or recreating the schema) between every test.** Works, but is
  dramatically slower at scale — the rollback pattern gives equivalent
  isolation for a fraction of the cost.
- **Relying on SQLite for CI speed without verifying dialect
  compatibility with the production database**, and being surprised months
  later when a Postgres-specific behavior (e.g., a `JSONB` query, a
  case-sensitivity difference, a constraint that Postgres enforces but
  SQLite doesn't) causes a production bug that no test ever caught.
- **Hand-writing every field of every test row**, producing tests where
  the meaningful, test-relevant field is buried among ten other required
  fields set to arbitrary values — `factory_boy` (or an equivalent
  factory-as-fixture pattern) keeps the noise down and the meaningful
  difference visible.
- **Session-scoping the database *connection/engine* correctly (Lesson 03)
  but forgetting to scope the actual per-test transaction/session
  narrowly** — this is the single most common source of cross-test data
  leakage in database test suites.

## Exercise Prompt (hand this to Claude Code)

> In `exercises/16-testing-databases/`, set up a small SQLAlchemy model
> `Invoice` (fields: `id`, `customer_email`, `amount`, `status` defaulting
> to `"draft"`) in `src/models.py`, and a function
> `finalize_invoice(session, invoice_id)` in `src/invoicing.py` that raises
> `ValueError` if the invoice is already `"finalized"`, otherwise sets
> `status = "finalized"` and commits. Use SQLite in-memory for this
> exercise (note in a comment that a real production setup would prefer
> `testcontainers` against Postgres, and why, per this lesson, but SQLite
> keeps the exercise dependency-free). Build a `conftest.py` implementing
> the full transactional-rollback fixture pattern (`db_engine` session-
> scoped, `db_session` function-scoped with begin/rollback), and an
> `InvoiceFactory` using `factory_boy`'s `SQLAlchemyModelFactory` with a
> `factory.Sequence` for `customer_email`. Write `tests/test_invoicing.py`
> with: (1) a test using the factory to create a draft invoice and
> asserting `finalize_invoice` correctly changes its status; (2) a test
> asserting `finalize_invoice` raises `ValueError` on an already-finalized
> invoice (built via the factory with `status="finalized"` passed as an
> override); (3) a test explicitly proving test isolation — create an
> invoice in one test function, then in a SEPARATE test function assert
> `session.query(Invoice).count() == 0` at the start, demonstrating the
> rollback actually cleared it. Add `factory_boy` and `Faker` to a
> `requirements-dev.txt`, pinned to real current versions.

## Quiz

1. In the transactional-rollback fixture pattern, the test code itself
   calls `session.commit()`. Why doesn't that commit persist to the real
   database once the test ends?
2. Why is it usually better to session-scope the database *engine* but
   function-scope the *session/transaction*, rather than picking one scope
   for both?
3. Give one concrete kind of bug that testing against SQLite could miss but
   testing against a real containerized Postgres would catch.
4. What specific problem does `factory.Sequence` solve that a hardcoded
   field value (e.g. `email = "test@example.com"` on every generated
   object) would run into?
5. You're testing a function whose logic is pure in-memory total
   calculation over a list of already-fetched order items — no SQL queries
   of its own. Per Lesson 10's taxonomy, is a real database, an in-memory
   SQLite database, or a fake repository the most appropriate choice, and
   why?

<details>
<summary>Answers</summary>

1. Because the fixture already opened an outer transaction on the
   connection before the test ran, and the ORM session is bound to that
   same connection. The test's `session.commit()` only commits *within*
   that outer, still-open transaction — it doesn't reach the database's
   actual committed state. The fixture's teardown then calls
   `transaction.rollback()` on the outer transaction, discarding everything
   that happened inside it, regardless of how many times the test itself
   called commit.
2. The engine (and the underlying connection pool/database server
   connection) is expensive to establish and stateless/reusable across
   tests, so session-scoping it avoids reconnecting for every test. The
   actual session/transaction needs to be function-scoped specifically so
   each test's changes are isolated and rolled back independently — sharing
   one transaction across many tests would mean one test's data is visible
   to (and could break) another, exactly the leakage risk covered in Lesson
   03.
3. Any behavior specific to the real production database engine's SQL
   dialect or constraint enforcement that SQLite doesn't replicate
   identically — e.g., a `JSONB`-specific query operator, strict foreign-key
   or check-constraint enforcement that SQLite handles more permissively by
   default, or case-sensitivity differences in string comparisons between
   the two engines.
4. It guarantees each generated object gets a unique value (e.g., a unique
   incrementing email address) across multiple factory calls within the
   same test or across tests in the same run. A hardcoded value would cause
   a real unique-constraint violation (or silent overwrite, depending on
   the field) the moment more than one object is created via the factory
   in the same test.
5. A fake repository (or, even more simply, no double at all if the
   function just takes plain data) is most appropriate — per Lesson 10's
   decision process, step 1 asks whether this is a real boundary at all.
   Since the function's logic is purely in-memory and doesn't touch SQL,
   there's no reason to pay for any database — real or SQLite — at all; a
   fake (or a plain constructed list of order items) gives the fastest,
   simplest, equally trustworthy test.

</details>

## Further Reading

- SQLAlchemy docs — [Joining a Session into an External Transaction (the rollback pattern)](https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
- factory_boy docs — [ORM integrations](https://factoryboy.readthedocs.io/en/stable/orms.html)
- testcontainers-python docs — [Getting started](https://testcontainers-python.readthedocs.io/en/latest/)

---
Previous: [15 — Testing HTTP & External Services](15-testing-http-and-external-services.md) · Next: [17 — Testing Async Code](17-testing-async-code.md)
