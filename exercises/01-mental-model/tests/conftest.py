import pytest


@pytest.fixture
def mock_priced_catalog():
    yield {"widget": 9.99}
