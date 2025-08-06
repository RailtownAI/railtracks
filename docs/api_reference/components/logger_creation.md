# Logger Creation

The Logger Creation component provides a utility function to obtain a logger, either a specific one or the root RT logger, for logging purposes. This component is essential for managing logging configurations and ensuring consistent logging behavior across the application.

**Version:** 0.0.1

**Component Contact:** @github_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Logger Creation component is primarily used to manage and configure loggers within the application. It allows developers to obtain a logger by name, which is a wrapper around the standard Python `logging` module, with additional functionality to reference the RT root logger. This ensures that all logging is centralized and can be easily managed.

### 1.1 Obtaining a Logger

The primary use case for this component is to obtain a logger for logging messages. This is crucial for debugging and monitoring the application.

python
from railtracks.utils.logging.create import get_rt_logger

# Obtain the root RT logger
logger = get_rt_logger()

# Obtain a specific logger
specific_logger = get_rt_logger("specific_name")


## 2. Public API

### `def get_rt_logger(name)`
A method used to get a logger of the provided name.

The method is essentially a wrapper of the `logging` method to collect the logger, but it will add a reference to
the RT root logger.

If the name is not provided it returns the root RT logger.


---

## 3. Architectural Design

The Logger Creation component is designed to provide a simple interface for obtaining loggers while ensuring that all loggers are part of the RT logging hierarchy. This design choice allows for centralized logging configuration and management.

### 3.1 Logger Hierarchy

- **RT Root Logger:** The root logger for the application, identified by the name `RT`. All other loggers are children of this root logger.
- **Logger Naming:** Loggers are named using the format `RT.<name>`, where `<name>` is the specific logger name provided by the user.

## 4. Important Considerations

### 4.1 Logger Configuration

- **Default Logger Name:** The default logger name is `RT`, as defined in the [config.py](../packages/railtracks/src/railtracks/utils/logging/config.py) file.
- **Colorful Logging:** The component supports colorful logging using the `ColorfulFormatter` class, which applies colors based on log levels and specific keywords.

## 5. Related Files

### 5.1 Code Files

- [`create.py`](../packages/railtracks/src/railtracks/utils/logging/create.py): Contains the `get_rt_logger` function for obtaining loggers.
- [`config.py`](../packages/railtracks/src/railtracks/utils/logging/config.py): Defines the RT logger name and provides various logger configurations.

### 5.2 Related Feature Files

- [`logging_profiling.md`](../docs/features/logging_profiling.md): (Not found) Expected to contain documentation related to logging and profiling features.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
