import pytest

from railtracks.observability import configure


@pytest.fixture(autouse=True)
def _reset_observability_state():
    """Reset the observability singleton state around every test.

    `configure._observer` gets swapped for a fresh Observer between tests so
    consumer tasks from a previous test's event loop don't leak forward.
    """
    configure.reset_for_tests()
    yield
    configure.reset_for_tests()
