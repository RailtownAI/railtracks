import pytest

from railtracks.observability_bridge import _state


@pytest.fixture(autouse=True)
def _reset_bridge_state():
    """Reset the observability_bridge singleton state around every test.

    Module-level globals in `_state.py` (_observer, _pending_writers, _started,
    etc.) would otherwise leak between tests. Reset before and after so an
    earlier failure doesn't corrupt later tests.
    """
    _state._reset_for_tests()
    yield
    _state._reset_for_tests()
