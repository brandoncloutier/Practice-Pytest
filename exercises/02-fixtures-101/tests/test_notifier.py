import pytest

from notifier import FakeMailClient, Notifier


# TODO: write a yield-fixture called `notifier` that:
#   1. constructs a fresh `FakeMailClient()`
#   2. calls `.connect()` on it
#   3. constructs a `Notifier(mail_client)` with it
#   4. yields the `Notifier` (the test runs here)
#   5. after the test runs, calls `.close()` on the mail client in teardown
#      and asserts the mail client's connection was closed (its `.closed`
#      flag should be True) — `FakeMailClient` already has a `.closed` flag,
#      it just isn't set until you call `.close()`
#
# @pytest.fixture
# def notifier():
#     ...


# TODO: write a yield-fixture called `traced_notifier` that depends on the
# built-in `request` fixture. During setup, build a fresh `FakeMailClient`
# and `Notifier` as above, but also stash `request.node.name` somewhere on
# the mail client (e.g. `mail_client.requested_by = request.node.name`) so a
# test can prove the fixture knows which test asked for it. Yield the
# `Notifier`. No special teardown needed beyond what you already wrote above
# (or leave teardown out entirely if you don't think it needs it — decide
# for yourself).
#
# @pytest.fixture
# def traced_notifier(request):
#     ...


def test_notify_appends_to_sent(notifier):
    notifier.notify(to="ada@example.com", subject="hello", body="world")

    assert notifier.mail_client.sent == [
        {"to": "ada@example.com", "subject": "hello", "body": "world"}
    ]


def test_notify_requires_prior_connect():
    mail_client = FakeMailClient()
    notifier = Notifier(mail_client)

    with pytest.raises(RuntimeError):
        notifier.notify(to="ada@example.com", subject="hello", body="world")


def test_traced_notifier_knows_its_test_name(traced_notifier):
    # This test's name is "test_traced_notifier_knows_its_test_name" — the
    # `traced_notifier` fixture should have captured that via `request.node.name`
    # during setup, without this test ever importing or using `request` itself.
    assert traced_notifier.mail_client.requested_by == "test_traced_notifier_knows_its_test_name"
