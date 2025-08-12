# Logging Configuration

The Logging Configuration component is responsible for setting up and managing logging for the Railtracks application, providing different logging levels and formats to facilitate effective monitoring and debugging.

**Version:** 0.0.1

**Component Contact:** @railtracks-dev

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Logging Configuration component is designed to provide a flexible and comprehensive logging system for the Railtracks application. It allows developers to configure logging levels, formats, and handlers to suit different environments and use cases, such as development, testing, and production.

### 1.1 Configuring Logging Levels

The component supports four logging levels:

- **VERBOSE**: Logs all messages, including debug information.
- **REGULAR**: Logs informational messages and above.
- **QUIET**: Logs warnings and above.
- **NONE**: Disables all logging.

python
import railtracks as rt

# Set logging to verbose
rt.ExecutorConfig(logging_setting="VERBOSE")

# Set logging to regular
rt.ExecutorConfig(logging_setting="REGULAR")

# Set logging to quiet
rt.ExecutorConfig(logging_setting="QUIET")

# Disable logging
rt.ExecutorConfig(logging_setting="NONE")


### 1.2 File Logging

Logs can be saved to a file by specifying a file path in the configuration.

python
import railtracks as rt

# Save logs to a file
rt.ExecutorConfig(log_file="my_logs.log")


## 2. Public API

### `class ColorfulFormatter(logging.Formatter)`
A simple formatter that can be used to format log messages with colours based on the log level and specific keywords.

#### `.__init__(self, fmt, datefmt)`
Class constructor.

#### `.format(self, record)`
No docstring found.


---
### `def setup_verbose_logger_config()`
Sets up the logger configuration in verbose mode.

Specifically that means:
- The console will log all messages (including debug)


---
### `def setup_regular_logger_config()`
Setups the logger in the regular mode. This mode will print all messages except debug messages to the console.


---
### `def setup_quiet_logger_config()`
Set up the logger to only log warning and above messages.


---
### `def setup_none_logger_config()`
Set up the logger to print nothing. This can be a useful optimization technique.


---
### `def setup_file_handler()`
Setups a logger file handler that will log messages to a file with the given name and logging level.


---
### `def prepare_logger()`
Prepares the logger based on the setting and optionally sets up the file handler if a path is provided.


---
### `def detach_logging_handlers()`
Shuts down the logging system and detaches all logging handlers.


---

## 3. Architectural Design

The Logging Configuration component is built around the Python `logging` module, with enhancements for color-coded output and flexible configuration. It uses a custom `ColorfulFormatter` to apply colors to log messages based on their level and specific keywords.

### 3.1 Design Considerations

- **ColorfulFormatter**: This class extends `logging.Formatter` to add color to log messages. It uses the `colorama` library to apply colors based on log levels and keywords.
- **Logging Levels**: The component provides functions to set up different logging configurations (`VERBOSE`, `REGULAR`, `QUIET`, `NONE`) using stream handlers.
- **File Logging**: The `setup_file_handler` function allows logs to be written to a file, with a default format that includes timestamps.
- **Custom Handlers**: Users can attach custom handlers to the logger for additional functionality, such as forwarding logs to external services.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Colorama**: The `colorama` library is used for coloring log messages. It is initialized with `autoreset=True` to ensure colors do not bleed into other outputs.
- **Logging Configuration**: The logging configuration should be set up at the start of the application to ensure all components log correctly.

### 4.2 Performance & Limitations

- **Logging Overhead**: Enabling verbose logging can introduce performance overhead due to the large volume of log messages. It is recommended to use this level only during development or troubleshooting.

## 5. Related Files

### 5.1 Code Files

- [`config.py`](../packages/railtracks/src/railtracks/utils/logging/config.py): Contains the implementation of the logging configuration component.

### 5.2 Related Component Files

- [`logging.md`](../docs/observability/logging.md): Provides additional context and examples for configuring and using logging in Railtracks.

## CHANGELOG

- **v0.0.1** (2023-10-01) [`<COMMIT_HASH>`]: Initial version.
