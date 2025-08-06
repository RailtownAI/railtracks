# Jupyter Compatibility

This component provides compatibility patches for MCP tools to function correctly in Jupyter notebooks, addressing I/O stream limitations.

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

The Jupyter Compatibility component is designed to ensure that MCP tools, which typically rely on standard I/O streams, can function seamlessly within Jupyter notebook environments. This is achieved by providing monkey patches for subprocess creation functions that are incompatible with Jupyter's custom I/O streams.

### 1.1 Subprocess Creation in Jupyter

In Jupyter notebooks, the standard I/O streams are replaced with custom implementations that do not support the `fileno()` method. This component provides patched versions of subprocess creation functions to handle this limitation.

python
from railtracks.rt_mcp.jupyter_compat import apply_patches

apply_patches()
# Now you can use MCP tools that rely on subprocess creation in Jupyter notebooks.


## 2. Public API

### `def is_jupyter()`
Check if we're running in a Jupyter notebook environment.

Returns:
    bool: True if running in a Jupyter notebook, False otherwise.


---
### `def patched_create_windows_process(command, args, env, errlog, cwd)`
Patched version of create_windows_process that works in Jupyter notebooks.

This function wraps the original create_windows_process function and handles
the case where errlog doesn't support fileno() in Jupyter notebooks.


---
### `def patched_create_windows_fallback_process(command, args, env, errlog, cwd)`
Patched version of _create_windows_fallback_process that works in Jupyter notebooks.

This function reimplements the original _create_windows_fallback_process function
to handle the case where errlog doesn't support fileno() in Jupyter notebooks.


---
### `def apply_patches()`
Apply the monkey patches to make MCP work in Jupyter notebooks.

This function patches the create_windows_process and _create_windows_fallback_process
functions in the mcp.os.win32.utilities module to make them work in Jupyter notebooks.

The patches are only applied if we're in a Jupyter environment.


---

## 3. Architectural Design

### 3.1 Design Considerations

- **Monkey Patching:** The component uses monkey patching to replace the original subprocess creation functions with versions that are compatible with Jupyter's I/O streams.
- **Environment Detection:** The `is_jupyter()` function is used to detect if the code is running within a Jupyter environment, ensuring that patches are only applied when necessary.
- **Error Handling:** The `_safe_stderr_for_jupyter()` function ensures that error logs are handled correctly, even when the standard error stream does not support `fileno()`.

## 4. Important Considerations

### 4.1 Implementation Details

- **Platform Specificity:** The patches are only applied on Windows platforms, as indicated by the `sys.platform.startswith("win")` check.
- **Single Application:** The patches are applied only once per session to prevent redundant operations, controlled by the `_patched` flag.
- **Fallback Mechanism:** If the patched subprocess creation with `creationflags` fails, a fallback mechanism without these flags is used to ensure compatibility.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/rt_mcp/jupyter_compat.py`](../packages/railtracks/src/railtracks/rt_mcp/jupyter_compat.py): Contains the implementation of the Jupyter compatibility patches.

### 5.2 Related Feature Files

- [`../features/mcp_integration.md`](../features/mcp_integration.md): Documents the integration of MCP tools with other systems, including Jupyter compatibility.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
