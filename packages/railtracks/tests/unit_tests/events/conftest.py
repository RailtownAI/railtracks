import pytest
import railtracks.context.central as central
from railtracks.observability import configure


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset the runner context and the observability singleton around each test."""
    central.delete_globals()
    configure.reset_for_tests()
    yield
    central.delete_globals()
    configure.reset_for_tests()
