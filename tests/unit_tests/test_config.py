import os
import uuid
import types
import pytest

from railtracks.config import ExecutorConfig

# ================= START ExecutorConfig: Fixtures ============
@pytest.fixture(params=["REGULAR", "DEBUG", "ERROR"])
def log_level(request):
    return request.param
# ================ END ExecutorConfig: Fixtures ===============

# ================= START ExecutorConfig: Instantiation tests ============

def test_instantiation_with_all_defaults():
    config = ExecutorConfig()
    assert isinstance(config.timeout, float)
    assert config.timeout == 150.0
    assert config.end_on_error is False
    assert config.logging_setting == "REGULAR"
    assert config.log_file is None
    assert isinstance(uuid.UUID(config.run_identifier), uuid.UUID)
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
        subscriber=test_subscriber,
        run_identifier=custom_run_identifier,
        prompt_injection=False
    )
    assert config.timeout == 12.0
    assert config.end_on_error is True
    assert config.logging_setting == log_level
    assert config.log_file == tmp_path / "logfile.txt"
    assert config.subscriber == test_subscriber
    assert config.run_identifier == custom_run_identifier
    assert config.prompt_injection is False

# ================ END ExecutorConfig: Instantiation tests ===============


# ================= START ExecutorConfig: run_identifier logic tests ============

def test_run_identifier_is_generated_if_none():
    config = ExecutorConfig(run_identifier=None)
    uuid_obj = uuid.UUID(config.run_identifier)
    assert isinstance(uuid_obj, uuid.UUID)

def test_run_identifier_is_used_when_given():
    identifier = "special-test-id"
    config = ExecutorConfig(run_identifier=identifier)
    assert config.run_identifier == identifier

# ================ END ExecutorConfig: run_identifier logic tests ===============


# ================= START ExecutorConfig: subscriber handling tests ============

def test_subscriber_accepts_callable():
    config = ExecutorConfig(subscriber=lambda s: s)
    assert callable(config.subscriber)

@pytest.mark.asyncio
async def test_subscriber_accepts_coroutine_function():
    async def async_sub_fn(text):
        return text
    config = ExecutorConfig(subscriber=async_sub_fn)
    # (not invoked/executed here, just type accepted)
    assert callable(config.subscriber)
    assert isinstance(config.subscriber, types.FunctionType)

def test_subscriber_is_none_by_default():
    config = ExecutorConfig()
    assert config.subscriber is None

# ================ END ExecutorConfig: subscriber handling tests ===============


# ================= START ExecutorConfig: logging_setting options tests ============

@pytest.mark.parametrize("log_setting", ["REGULAR", "ERROR", "DEBUG"])
def test_logging_setting_accepts_allowable_levels(log_setting):
    config = ExecutorConfig(logging_setting=log_setting)
    assert config.logging_setting == log_setting

def test_logging_setting_default_is_regular():
    config = ExecutorConfig()
    assert config.logging_setting == "REGULAR"

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