# Lesson 15 — Testing HTTP & External Services

Phase 5: Testing Real-World Systems

## Learning Objectives

- Explain why raw `mocker.patch` on individual `requests` calls is usually
  the wrong tool once an HTTP integration has more than trivial shape.
- Use `responses` to mock `requests`-based HTTP calls at the transport
  layer, including status codes, JSON bodies, and error simulation.
- Know that `respx` is the equivalent tool for `httpx`-based code, and why
  the client library you use determines which mocking library applies.
- Distinguish what you should verify with these tools versus what belongs
  in a real (if infrequent) integration test against a sandbox/staging
  endpoint.

## Why This Matters in Production

Nearly every production service talks to at least one external HTTP API.
The naive approach — `mocker.patch("myclient.requests.get")` — works for a
single call, but degrades badly once a client makes several calls, needs
different responses for different URLs, or needs to simulate network-level
failures (timeouts, connection errors) rather than just "the function
returned a `Mock`." Purpose-built HTTP mocking libraries intercept at the
transport layer instead, which means your actual client code — URL
construction, header handling, retry logic, JSON parsing — runs for real
against a fake network, giving you a meaningfully stronger test than mocking
your own wrapper function ever could.

## Concept: Why Not Just `mocker.patch` the Call?

```python
# The naive approach
def test_get_user(mocker):
    mock_get = mocker.patch("myclient.requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"id": 1, "name": "Ada"}

    user = get_user(1)
    assert user["name"] == "Ada"
```

This works, but notice what it *doesn't* verify: it doesn't check that
`get_user` actually built the right URL, sent the right headers, or used the
right HTTP method — because `requests.get` itself never ran; you replaced it
entirely with a `Mock` you configured to answer however you wanted,
regardless of what arguments it was called with (unless you also add
explicit `assert_called_with` checks, which is extra bookkeeping this
approach forces on every test). It also means you'd need a completely
different, ad hoc setup to simulate "the server returned a 500" versus "the
connection timed out" versus "the response body was malformed JSON" — each
one is just more manual `Mock` configuration, drifting further from what a
real `requests.Response` object actually looks like.

## Concept: `responses` — Mocking at the Transport Layer

`responses` (for the `requests` library specifically) intercepts HTTP calls
at the point where `requests` would actually hit the network, and returns a
registered fake response instead — meaning your real client code, URL
building, and header logic all still run exactly as they would in
production; only the actual socket connection is faked.

```python
import responses
import requests

@responses.activate
def test_get_user_success():
    responses.add(
        responses.GET,
        "https://api.example.com/users/1",
        json={"id": 1, "name": "Ada Lovelace"},
        status=200,
    )
    user = get_user(1)   # real function, real URL construction, real requests.get call
    assert user["name"] == "Ada Lovelace"

@responses.activate
def test_get_user_not_found():
    responses.add(
        responses.GET,
        "https://api.example.com/users/999",
        json={"error": "not found"},
        status=404,
    )
    with pytest.raises(UserNotFoundError):
        get_user(999)

@responses.activate
def test_get_user_network_failure():
    responses.add(
        responses.GET,
        "https://api.example.com/users/1",
        body=requests.exceptions.ConnectionError("simulated network failure"),
    )
    with pytest.raises(requests.exceptions.ConnectionError):
        get_user(1)
```

Because `responses` matches on the actual URL (and, optionally, method,
query params, and request body), a test using it also implicitly verifies
your code constructed the right request in the first place — a
`responses.ConnectionError` (URL not registered/matched) is exactly the
failure you'd get if `get_user` built the wrong URL, which is a real,
useful assertion the naive `mocker.patch` approach doesn't give you for
free.

You can also assert on what was actually sent, after the fact:

```python
@responses.activate
def test_create_user_sends_correct_payload():
    responses.add(responses.POST, "https://api.example.com/users",
                   json={"id": 2}, status=201)
    create_user(name="Bob", email="bob@example.com")

    assert len(responses.calls) == 1
    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body == {"name": "Bob", "email": "bob@example.com"}
```

## Concept: The Client Library Determines the Tool

`responses` only intercepts `requests`-based calls, because it hooks into
`requests`'s own transport adapter mechanism. If your codebase uses `httpx`
instead (increasingly common, especially for async code — see Lesson 17),
you need **`respx`**, which does the equivalent job for `httpx`'s transport
layer. The concepts transfer directly (register a URL/method → fake
response, assert on what was actually sent), but the library has to match
the HTTP client your code actually uses — there's no universal HTTP-mocking
tool that works underneath every client library, because each one has its
own internal transport hook that needs a purpose-built interception layer.
Check which HTTP client a codebase uses before reaching for either.

## Concept: What Still Belongs in a Real Integration Test

Transport-layer mocking is excellent for verifying *your* code's behavior —
URL construction, retry logic, error handling, response parsing — cheaply
and deterministically. It cannot verify that the *external API itself*
still behaves the way your fake responses assume it does. If the real
API changes its response shape, deprecates a field, or starts requiring a
new header, every `responses`-mocked test keeps passing regardless, because
the fake responses were hand-authored to match a snapshot of the API's
contract at the time you wrote the test.

This is why most production systems complement mocked unit tests with a
small number of real integration tests — run less frequently (Lesson 12's
`@pytest.mark.integration`, run on a schedule or a slower CI stage, not on
every push) that hit a real sandbox/staging endpoint (or a contract-testing
tool) and would fail if the real API's actual behavior drifted from what
your mocks assume. The mocked tests answer "does my code do the right thing
given this response shape"; the integration tests answer "is that response
shape still accurate." Both are needed; neither substitutes for the other.

## Common Pitfalls

- **Mocking your own thin wrapper function instead of the transport
  layer**, silently no longer testing URL construction, header logic, or
  serialization — the naive approach shown at the top of this lesson.
- **Hand-authored fake JSON responses drifting from the real API's actual
  shape over time**, with nothing catching the drift because the mocked
  tests only check internal consistency against themselves. Periodic real
  integration tests (or a contract-testing tool) are the mitigation.
- **Forgetting `@responses.activate`** (or the `RequestsMock` context
  manager) on a test, which means `requests` tries to make a **real**
  network call — slow, flaky, and a potential security/data concern in CI
  if it succeeds against a real, unintended endpoint.
- **Not testing failure paths (timeouts, 500s, malformed JSON) at all**,
  because it's marginally more setup than the happy path — `responses`
  makes simulating these cheap; there's little excuse not to cover at
  least the failure modes your code has explicit handling for.
- **Using the wrong library for the HTTP client actually in use** (e.g.
  reaching for `responses` on an `httpx`-based codebase, where it has no
  effect at all because `httpx` doesn't route through `requests`'s
  transport layer).

## Exercise Prompt (hand this to Claude Code)

> In `exercises/15-http-mocking/`, create `src/weather_client.py` with a
> `get_current_temperature(city: str) -> float` function using `requests`
> to call `GET https://api.weather.example.com/v1/current?city={city}`,
> parsing `response.json()["temp_celsius"]`, raising a custom
> `WeatherServiceError` on a non-2xx status or a `requests.
> exceptions.RequestException`, and raising `ValueError` if the response
> JSON is missing the expected key. Add `responses` to a
> `requirements-dev.txt` in this folder pinned to a real current version.
> Then write `tests/test_weather_client.py` covering: (1) a success case
> using `responses.add` with a realistic JSON body; (2) a 404/error-status
> case asserting `WeatherServiceError` is raised; (3) a simulated
> `requests.exceptions.ConnectionError` case, also asserting
> `WeatherServiceError` (or that the original exception propagates —
> decide and document which behavior the function should have, then
> implement it to match); (4) a malformed-JSON-body case (valid JSON,
> missing the `temp_celsius` key) asserting `ValueError`; (5) one test
> asserting on `responses.calls[0].request.url` to prove the city parameter
> was correctly URL-encoded for a city name containing a space (e.g. "New
> York"). Leave test (5) for me to write from a docstring TODO, worked
> examples for the rest.

## Quiz

1. What does `mocker.patch("myclient.requests.get")` fail to verify about
   your own code that `responses` verifies for free, just by how it
   matches requests?
2. Your codebase switches its HTTP client from `requests` to `httpx`. What
   happens to your existing `responses`-based tests, and what do you need
   instead?
3. Give a concrete scenario where a `responses`-mocked test suite could be
   100% green while the integration with the real external API is
   completely broken in production.
4. Why is simulating a `ConnectionError` (not just a non-2xx status code)
   worth a dedicated test, distinct from testing a 500 response?
5. What's the practical argument for keeping a small number of real,
   infrequent integration tests alongside a much larger set of
   `responses`-mocked unit tests, rather than relying on mocked tests
   alone?

<details>
<summary>Answers</summary>

1. It doesn't verify that your code actually constructed the correct URL,
   HTTP method, headers, or request body — because the real `requests.get`
   call never happens at all; you replaced it wholesale with a `Mock`
   configured to answer however the test wants, independent of what
   arguments it was actually called with (unless you add explicit
   `assert_called_with` checks yourself). `responses` matches against the
   real URL/method your code actually sends, so a wrong URL fails the test
   naturally, without any extra assertion.
2. They stop being meaningful — `responses` hooks into `requests`'s own
   transport adapter, so it has no effect on `httpx` calls, which route
   through a completely different internal mechanism. `httpx`-based tests
   never actually get intercepted by `responses`, meaning those tests would
   either fail (trying a real network call) or need to be rewritten. You'd
   need `respx`, the equivalent transport-layer mocking library built
   specifically for `httpx`.
3. If the real API changes its response shape (renames a field, removes
   one your parsing code depends on, changes error response structure) after
   your `responses`-mocked tests were written, the mocked tests keep
   passing indefinitely — they only check that your code behaves correctly
   against the *hand-authored fake* response, which no longer reflects
   reality. Nothing in a purely mocked test suite can detect that the real
   API's actual behavior has drifted.
4. Because they're genuinely different failure modes your code may need to
   handle differently: a 500 means the server responded (you have a real,
   parseable HTTP response with a status code and possibly a body) whereas
   a `ConnectionError` means no response was received at all (network
   failure, DNS failure, connection refused). Code that only handles
   "check `response.status_code`" logic will crash on a `ConnectionError`
   with an unhandled exception instead of the intended error-handling path,
   which only a dedicated test simulating that specific failure mode would
   catch.
5. Mocked unit tests verify your own code's logic cheaply, deterministically,
   and quickly, but their correctness depends entirely on the mocked
   responses accurately reflecting the real API — an assumption that can
   silently go stale. A small number of real integration tests, even run
   infrequently, provide the only actual verification that the real
   external system still behaves the way your mocks assume, catching
   contract drift that no amount of well-designed mocked tests could ever
   detect on their own.

</details>

## Further Reading

- `responses` — [GitHub project and usage docs](https://github.com/getsentry/responses)
- `respx` — [Documentation for mocking httpx](https://lundberg.github.io/respx/)
- `requests` docs — [Exceptions reference (for simulating failure modes accurately)](https://requests.readthedocs.io/en/latest/api/#exceptions)

---
Previous: [14 — Coverage & Test Quality](14-coverage-and-test-quality.md) · Next: [16 — Testing Databases & Persistence](16-testing-databases-and-persistence.md)
