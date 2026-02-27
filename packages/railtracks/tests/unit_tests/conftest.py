import pytest
import railtracks as rt


@pytest.fixture(autouse=True)
def disable_session_persistence(monkeypatch):
    original_session = rt.session

    def test_session_wrapper(*args, **kwargs):
        kwargs["save_state"] = False
        return original_session(*args, **kwargs)

    monkeypatch.setattr(rt, "session", test_session_wrapper)


# ====================================== MockLLM ======================================


# ===================================== END MockLLM ======================================