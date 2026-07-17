import pytest

from railtracks.observability import singleton


@pytest.fixture(autouse=True)
def _reset_observability_singleton():
    """Reset the observability singleton state around every test.

    Module-level globals in `singleton.py` (_observer, _pending_writers,
    _started, _start_lock) would otherwise leak between tests. This is a
    no-op for Feature 1's tests that use their own Observer instances.
    """
    singleton._reset_for_tests()
    yield
    singleton._reset_for_tests()
