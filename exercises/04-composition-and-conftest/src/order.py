"""Order domain object used by the tests/unit/conftest.py make_order factory."""


class Order:
    def __init__(self, items, status="pending"):
        self.items = items
        self.status = status

    def cancel(self):
        if self.status != "pending":
            raise ValueError(f"cannot cancel an order with status {self.status!r}")
        self.status = "cancelled"
