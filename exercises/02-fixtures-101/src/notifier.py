"""A tiny notification module for practicing fixture setup/teardown.

Notifier wraps a "mail client" that has to be connected before sending
and closed afterward, giving fixtures something real to set up and tear
down.
"""


class FakeMailClient:
    """In-memory stand-in for a real outbound mail client. No network calls."""

    def __init__(self):
        self.connected = False
        self.closed = False
        self.sent = []

    def connect(self):
        self.connected = True

    def send(self, to, subject, body):
        if not self.connected:
            raise RuntimeError("mail client is not connected")
        self.sent.append({"to": to, "subject": subject, "body": body})

    def close(self):
        self.connected = False
        self.closed = True


class Notifier:
    """Sends notifications through a mail client."""

    def __init__(self, mail_client):
        self.mail_client = mail_client

    def notify(self, to, subject, body):
        self.mail_client.send(to, subject, body)
