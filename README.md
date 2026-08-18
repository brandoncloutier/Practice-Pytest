# Pytest for Production: A Structured Curriculum

Welcome. This is a self-paced curriculum for going from "I use Mock, MagicMock,
`pytest.mark.parametrize`, `monkeypatch`, and `patch`" to "I can architect a test
suite for a production codebase and make deliberate, defensible choices about
how to test it."

## Who this is for

You already know the vocabulary of pytest and `unittest.mock`. This curriculum
does not re-teach "what is a unit test." Instead it fills in the gaps that
usually separate someone who *uses* these tools from someone who *reasons*
about them: fixture lifecycle and composition, exactly what `patch()` is doing
under the hood and why "patch where it's used" is the rule, when `monkeypatch`
beats `mock.patch` (and vice versa), how to choose the right test double
instead of reflexively mocking everything, and how test suites are organized,
run, and trusted at scale in a real engineering org.

## How this curriculum is structured

21 lessons across 6 phases, plus a capstone. Each phase builds on the last —
do them in order the first time through.

| Phase | Lessons | Theme |
|---|---|---|
| 1. Foundations Refresher | 01–02 | The mental model you're probably missing pieces of |
| 2. Fixtures & Parametrization Mastery | 03–05 | The part of pytest that isn't "just unittest with less boilerplate" |
| 3. Mocking Mastery | 06–10 | Going from "I called `patch`" to "I know why it worked" |
| 4. Production Test Design | 11–14 | Making suites readable, trustworthy, and fast |
| 5. Testing Real-World Systems | 15–18 | HTTP, databases, async, property-based testing |
| 6. Team & Pipeline Practices | 19–20 | CI, tooling, flaky tests, anti-patterns |
| Capstone | 21 | Put it all together on a small production-like service |

See [`curriculum/00-roadmap.md`](curriculum/00-roadmap.md) for the full lesson
list with one-line descriptions, and [`PROGRESS.md`](PROGRESS.md) for a
checklist to track yourself through it.

## Lesson format

Every lesson in `curriculum/` follows the same shape:

1. **Learning objectives** — what you'll be able to do afterward.
2. **Why it matters in production** — the motivating failure mode or cost.
3. **Concepts, with examples** — explanations paired with runnable code.
4. **Common pitfalls** — mistakes that pass code review but bite later.
5. **Hands-on exercise prompt** — a spec for a coding exercise, written so
   you can hand it directly to Claude Code (see below).
6. **Quiz** — 5 questions to check understanding, answers included in a
   collapsed `<details>` block so you can self-test honestly.
7. **Further reading** — links to primary sources (official docs), not blogs.

## How to use this with Claude Code

The lessons are deliberately *reading and reasoning* material — prose,
examples, and quizzes. The **exercises are meant to be built as code**, and
each lesson ends with an "Exercise Prompt" section written specifically so
you can paste it to Claude Code as-is. A typical flow per lesson:

1. Read the lesson file.
2. Take the quiz *before* looking at the answers — write your answers down.
3. Check your answers against the `<details>` block.
4. Copy the "Exercise Prompt" at the end of the lesson and give it to Claude
   Code in this repo (e.g. `mkdir exercises/03-fixture-scopes && cd $_` then
   ask Claude Code to scaffold it from the prompt). Ask Claude Code to
   generate the module *and a failing-first version* where useful, so you
   practice diagnosing failures, not just reading passing tests.
5. Run the tests yourself (`pytest -v`) and read the output before asking
   Claude Code to explain anything — the goal is your own pattern-matching,
   not delegated understanding.
6. When you're done, ask Claude Code for a short code review of the tests
   *you* wrote for the exercise — not the ones it generated for you — and
   check off the lesson in `PROGRESS.md`.

Suggested repo layout as you go:

```
practice-pytest/
  curriculum/          <- lesson files (this content)
  exercises/
    03-fixture-scopes/
    05-parametrization/
    ...
  PROGRESS.md
```

## Environment setup

You'll want a virtual environment and a consistent baseline dependency set.
Versions below were current as of August 2026 — pin what's actually resolved
in your lockfile, don't hand-copy these numbers indefinitely.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install "pytest>=8" pytest-mock pytest-cov pytest-xdist pytest-asyncio hypothesis
```

Additional libraries get called out in the specific lessons that need them
(`responses` or `respx` for HTTP mocking, `factory_boy` for test data,
`mutmut` for mutation testing, etc.) so you install them only when relevant.

## A note on grounding

Every factual claim about pytest/mock/library behavior in these lessons was
checked against current official documentation rather than written from
memory alone (pytest's own docs, the Python `unittest.mock` docs, and each
library's PyPI/readthedocs page). Version numbers were accurate as of
**August 2026** — always prefer what `pip show <package>` and the official
docs tell you over what's written here if they disagree.

## Start here

→ [`curriculum/00-roadmap.md`](curriculum/00-roadmap.md)
→ [`curriculum/01-the-pytest-mental-model.md`](curriculum/01-the-pytest-mental-model.md)
