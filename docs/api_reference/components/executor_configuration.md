# Executor Configuration

The `ExecutorConfig` class is a configuration object designed to allow customization of the executor in the RT (RailTracks) system. It provides various settings to control the behavior of the executor, such as timeout, error handling, logging, and more.

**Version:** 0.0.1

**Component Contact:** @developer_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The `ExecutorConfig` class is primarily used to configure the behavior of an executor within the RT system. It allows developers to specify settings such as timeout duration, error handling preferences, logging configurations, and more. This flexibility is crucial for tailoring the executor's behavior to specific use cases and operational requirements.

### 1.1 Configuring Timeout and Error Handling

The `ExecutorConfig` allows setting a timeout for the executor's operations and determining whether the executor should stop on encountering an error.

python
config = ExecutorConfig(timeout=120.0, end_on_error=True)


### 1.2 Customizing Logging

Developers can specify the logging level and the log file location to capture the executor's activities.

python
config = ExecutorConfig(logging_setting="DEBUG", log_file="executor.log")


## 2. Public API

### `class ExecutorConfig`
No docstring found.

#### `.__init__(self)`
ExecutorConfig is special configuration object designed to allow customization of the executor in the RT system.

Args:
    timeout (float): The maximum number of seconds to wait for a response to your top level request
    end_on_error (bool): If true, the executor will stop execution when an exception is encountered.
    logging_setting (allowable_log_levels): The setting for the level of logging you would like to have.
    log_file (str | os.PathLike | None): The file to which the logs will be written. If None, no file will be created.
    run_identifier (str | None): You can specify a run identifier to be used for this run. If None, a random UUID will be generated.
    broadcast_callback (Callable or Coroutine): A function or coroutine that will handle streaming messages.
    prompt_injection (bool): If true, prompts can be injected with global context
    save_state (bool): If true, the state of the executor will be saved to disk.

#### `.precedence_overwritten(self)`
If any of the parameters are provided (not None), it will create a new update the current instance with the new values and return a deep copied reference to it.


---

## 3. Architectural Design

The `ExecutorConfig` class is designed with flexibility and extensibility in mind. It encapsulates various configuration options that can be easily adjusted to meet different operational needs.

### 3.1 Design Considerations

- **Flexibility:** The class provides a wide range of configuration options, allowing for fine-tuned control over the executor's behavior.
- **Extensibility:** New configuration options can be added with minimal impact on existing functionality.
- **Ease of Use:** The class is designed to be intuitive, with sensible defaults and clear parameter descriptions.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The `ExecutorConfig` class relies on the `allowable_log_levels` from the `railtracks.utils.logging.config` module to determine valid logging levels.

### 4.2 Performance & Limitations

- The `timeout` parameter should be set considering the expected duration of operations to avoid premature termination.
- The `end_on_error` setting should be used judiciously, as stopping on errors might not be desirable in all scenarios.

## 5. Related Files

### 5.1 Code Files

- [`../utils/config.py`](../utils/config.py): Contains the implementation of the `ExecutorConfig` class.

### 5.2 Related Component Files

- [`../logging_profiling.md`](../logging_profiling.md): Discusses logging and profiling features related to the executor configuration.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
