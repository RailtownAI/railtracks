import pytest

from railtracks.observability import configure, publish


@pytest.fixture(autouse=True)
def _reset_observability_state():
    """Reset the observability singleton state around every test.

    Module-level globals in `configure.py` (_observer, _pending_writers,
    _started, _start_lock) and `publish.py` (_pending_tasks) would otherwise
    leak between tests. No-op for Feature 1's tests that use their own
    Observer instances.
    """
    configure.reset_for_tests()
    publish.reset_for_tests()
    yield
    configure.reset_for_tests()
    publish.reset_for_tests()
