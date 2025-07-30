"""
Jupyter compatibility module for MCP tools.

This module provides monkey patches for MCP functions that don't work in Jupyter notebooks
due to I/O stream limitations. Specifically, it patches the subprocess creation functions
to avoid using `fileno()` on Jupyter's custom I/O streams.
"""

import io
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, TextIO, TypeVar

try:
    from mcp.os.win32.utilities import (
        create_windows_process as original_create_windows_process,
    )
except ImportError:
    original_create_windows_process = None

# Type variables for function signatures
T = TypeVar("T")
R = TypeVar("R")

# Flag to track if patches have been applied
_patched = False


def is_jupyter() -> bool:
    """
    Check if we're running in a Jupyter notebook environment.

    Returns:
        bool: True if running in a Jupyter notebook, False otherwise.
    """
    try:
        # Try to import it directly (in case we're in a module)
        try:
            from IPython import get_ipython
        except ImportError:
            return False

        # Check the shell type
        ipython = get_ipython()
        if ipython is None:
            return False
        shell = ipython.__class__.__name__

        # Check for various Jupyter environments
        if (
            "google.colab" in str(ipython.__class__) or shell == "ZMQInteractiveShell"
        ):  # Jupyter notebook or qtconsole
            return True
        elif shell == "TerminalInteractiveShell":  # Terminal running IPython
            return False
        else:
            return False
    except (NameError, AttributeError):
        return False


def _safe_stderr_for_jupyter(errlog: Optional[TextIO] = None) -> Optional[TextIO]:
    """
    Create a safe stderr for Jupyter environments that doesn't require fileno().

    Args:
        errlog: The original error log stream, or None to use sys.stderr

    Returns:
        A file object that can be used as stderr in subprocess.Popen, or None to use subprocess.DEVNULL
    """
    if errlog is None:
        errlog = sys.stderr

    # If we're not in Jupyter, just return the original errlog
    if not is_jupyter():
        return errlog

    # In Jupyter, we need to avoid using streams that don't support fileno()
    try:
        # Try to get the fileno - if this works, we can use the original stream
        errlog.fileno()
        return errlog
    except (AttributeError, IOError, ValueError, io.UnsupportedOperation):
        # If fileno() is not supported, use DEVNULL
        # We could also redirect to a temporary file if logging is important
        return None  # None will be converted to subprocess.DEVNULL in the patched functions


async def patched_create_windows_process(
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
    errlog: TextIO | None = sys.stderr,
    cwd: Path | str | None = None,
) -> Any:  # Return type matches original function
    """
    Patched version of create_windows_process that works in Jupyter notebooks.

    This function wraps the original create_windows_process function and handles
    the case where errlog doesn't support fileno() in Jupyter notebooks.
    """
    # Use a safe stderr that works in Jupyter
    safe_errlog = _safe_stderr_for_jupyter(errlog)

    # Call the original function with the safe stderr
    return await original_create_windows_process(
        command=command, args=args, env=env, errlog=safe_errlog, cwd=cwd
    )


async def patched_create_windows_fallback_process(
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
    errlog: TextIO | None = sys.stderr,
    cwd: Path | str | None = None,
) -> Any:  # Return type matches original function
    """
    Patched version of _create_windows_fallback_process that works in Jupyter notebooks.

    This function reimplements the original _create_windows_fallback_process function
    to handle the case where errlog doesn't support fileno() in Jupyter notebooks.
    """
    # Use a safe stderr that works in Jupyter
    safe_errlog = _safe_stderr_for_jupyter(errlog)

    # Convert None to DEVNULL for stderr
    stderr_param = subprocess.DEVNULL if safe_errlog is None else safe_errlog

    try:
        # Try launching with creationflags to avoid opening a new console window
        popen_obj = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_param,
            env=env,
            cwd=cwd,
            bufsize=0,  # Unbuffered output
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        # If creationflags failed, fallback without them
        popen_obj = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_param,
            env=env,
            cwd=cwd,
            bufsize=0,
        )

    # Return the same type of object as the original function
    from mcp.os.win32.utilities import FallbackProcess

    return FallbackProcess(popen_obj)


def apply_patches() -> None:
    """
    Apply the monkey patches to make MCP work in Jupyter notebooks.

    This function patches the create_windows_process and _create_windows_fallback_process
    functions in the mcp.os.win32.utilities module to make them work in Jupyter notebooks.

    The patches are only applied if we're in a Jupyter environment.
    """
    if not sys.platform.startswith("win"):
        return

    global _patched

    # Only apply patches once
    if _patched:
        return

    # Only apply patches in Jupyter
    if not is_jupyter():
        return

    # Import the module we need to patch
    import mcp.os.win32.utilities

    # Apply the patches
    mcp.os.win32.utilities.create_windows_process = patched_create_windows_process
    mcp.os.win32.utilities._create_windows_fallback_process = (
        patched_create_windows_fallback_process
    )

    _patched = True
