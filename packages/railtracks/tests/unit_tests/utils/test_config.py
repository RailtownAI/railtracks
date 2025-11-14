import os
import uuid
import types
import pytest

from railtracks.utils.config import ExecutorConfig

# ================= START ExecutorConfig: Fixtures ============
@pytest.fixture(params=["INFO", "DEBUG"])
def log_level(request):
    return request.param
# ================ END ExecutorConfig: Fixtures ===============

# ================= START ExecutorConfig: Instantiation tests ============

def test_instantiation_with_all_defaults():
    config = ExecutorConfig()
    assert isinstance(config.timeout, float)
    assert config.timeout == 150.0
    assert config.end_on_error is False
    assert config.logging_setting == "INFO"
    assert config.log_file is None
    assert config.prompt_injection is True
    assert config.subscriber is None

def test_instantiation_with_custom_values(tmp_path, log_level):
    test_subscriber = lambda x: x
    custom_run_identifier = "my-id-123"
    config = ExecutorConfig(
        timeout=12.0,
        end_on_error=True,
        logging_setting=log_level,       
        log_file=tmp_path / "logfile.txt",
        broadcast_callback=test_subscriber,
        prompt_injection=False
    )
    assert config.timeout == 12.0
    assert config.end_on_error is True
    assert config.logging_setting == log_level
    assert config.log_file == tmp_path / "logfile.txt"
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


# ================= START ExecutorConfig: logging_setting options tests ============

@pytest.mark.parametrize("log_setting", ["INFO", "DEBUG"])
def test_logging_setting_accepts_allowable_levels(log_setting):
    config = ExecutorConfig(logging_setting=log_setting)
    assert config.logging_setting == log_setting

def test_logging_setting_default_is_regular():
    config = ExecutorConfig()
    assert config.logging_setting == "INFO"

# ================ END ExecutorConfig: logging_setting options tests ===============


# ================= START ExecutorConfig: log_file type tests ============
def test_log_file_accepts_filename_as_string():
    config = ExecutorConfig(log_file="log.txt")
    assert config.log_file == "log.txt"

def test_log_file_accepts_os_pathlike():
    pathlike = os.path.join("var", "log", "exec.log")
    config = ExecutorConfig(log_file=pathlike)
    assert config.log_file == pathlike

def test_log_file_accepts_tmp_path_fixture(tmp_path):
    config = ExecutorConfig(log_file=tmp_path)
    assert config.log_file == tmp_path

def test_log_file_default_is_none():
    config = ExecutorConfig()
    assert config.log_file is None

# ================ END ExecutorConfig: log_file type tests ===============


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
        logging_setting="INFO",
        prompt_injection=True,
        save_state=True
    )

def test_updated_timeout(base_config):
    updated_config = base_config.precedence_overwritten(timeout=200.0)
    assert updated_config.timeout == 200.0
    assert updated_config.end_on_error == base_config.end_on_error
    assert updated_config.logging_setting == base_config.logging_setting
    assert updated_config.log_file == base_config.log_file
    assert updated_config.prompt_injection == base_config.prompt_injection

def test_multiple_updated(base_config):
    updated_config = base_config.precedence_overwritten(
        timeout=200.0,
        end_on_error=False,
        logging_setting="CRITICAL",
        log_file="new_log.txt",
        prompt_injection=False
    )
    assert updated_config.timeout == 200.0
    assert updated_config.end_on_error is False
    assert updated_config.logging_setting == "CRITICAL"
    assert updated_config.log_file == "new_log.txt"
    assert updated_config.prompt_injection is False

    assert base_config.timeout == 100.0
    assert base_config.log_file is None