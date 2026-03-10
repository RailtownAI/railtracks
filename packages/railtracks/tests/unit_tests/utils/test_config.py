import uuid
import types
import pytest

from railtracks.utils.config import ExecutorConfig

# ================= START ExecutorConfig: Instantiation tests ============

def test_instantiation_with_all_defaults():
    config = ExecutorConfig()
    assert config.timeout is None
    assert config.end_on_error is False
    assert config.prompt_injection is True
    assert config.subscriber is None

def test_instantiation_with_custom_values(tmp_path):
    test_subscriber = lambda x: x
    config = ExecutorConfig(
        timeout=12.0,
        end_on_error=True,
        broadcast_callback=test_subscriber,
        prompt_injection=False
    )
    assert config.timeout == 12.0
    assert config.end_on_error is True
    assert config.subscriber == test_subscriber
    assert config.prompt_injection is False

# ================ END ExecutorConfig: Instantiation tests ===============




# ================= START ExecutorConfig: broadcast_callback handling tests ============

def test_subscriber_accepts_callable():
    config = ExecutorConfig(broadcast_callback=lambda s: s)
    assert callable(config.subscriber)

@pytest.mark.asyncio
async def test_subscriber_accepts_coroutine_function():
    async def async_sub_fn(text):
        return text
    config = ExecutorConfig(broadcast_callback=async_sub_fn)
    # (not invoked/executed here, just type accepted)
    assert callable(config.subscriber)
    assert isinstance(config.subscriber, types.FunctionType)

def test_subscriber_is_none_by_default():
    config = ExecutorConfig()
    assert config.subscriber is None

# ================ END ExecutorConfig: broadcast_callback handling tests ===============


# ================= START ExecutorConfig: prompt_injection tests ============

def test_prompt_injection_default_true():
    config = ExecutorConfig()
    assert config.prompt_injection is True

def test_prompt_injection_false_when_overridden():
    config = ExecutorConfig(prompt_injection=False)
    assert config.prompt_injection is False

# ================ END ExecutorConfig: prompt_injection tests ===============

# ================= START Precedence Overwritten Tests ============
@pytest.fixture
def base_config():
    return ExecutorConfig(
        timeout=100.0,
        end_on_error=True,
        prompt_injection=True,
        save_state=True
    )

def test_updated_timeout(base_config):
    updated_config = base_config.precedence_overwritten(timeout=200.0)
    assert updated_config.timeout == 200.0
    assert updated_config.end_on_error == base_config.end_on_error
    assert updated_config.prompt_injection == base_config.prompt_injection

def test_multiple_updated(base_config):
    updated_config = base_config.precedence_overwritten(
        timeout=200.0,
        end_on_error=False,
        prompt_injection=False
    )
    assert updated_config.timeout == 200.0
    assert updated_config.end_on_error is False
    assert updated_config.prompt_injection is False

    assert base_config.timeout == 100.0

def test_timeout_none_by_default():
    """Default timeout should be None (disabled)."""
    config = ExecutorConfig()
    assert config.timeout is None

def test_timeout_none_explicit():
    """Explicitly passing timeout=None should disable the timeout."""
    config = ExecutorConfig(timeout=None)
    assert config.timeout is None

def test_precedence_overwritten_timeout_none_disables(base_config):
    """precedence_overwritten(timeout=None) should set timeout to None (disabled)."""
    assert base_config.timeout == 100.0
    updated_config = base_config.precedence_overwritten(timeout=None)
    assert updated_config.timeout is None

def test_precedence_overwritten_without_timeout_disables(base_config):
    """Calling precedence_overwritten() without specifying timeout disables the timeout (None == not provided)."""
    updated_config = base_config.precedence_overwritten()
    assert updated_config.timeout is None

def test_precedence_overwritten_timeout_float_enables(base_config):
    """Calling precedence_overwritten(timeout=float) should set the timeout to that float."""
    updated_config = base_config.precedence_overwritten(timeout=42.0)
    assert updated_config.timeout == 42.0