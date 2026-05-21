import os
import warnings
from pathlib import Path

_DIRNAME = ".railtracks"


def resolve_railtracks_home() -> Path:
    """Return the .railtracks directory path.

    Resolution order:
    1. RAILTRACKS_HOME env var — .railtracks is created inside this directory.
    2. Walk up from cwd() looking for an existing .railtracks directory.
    3. Fall back to cwd()/.railtracks with a UserWarning.
    """
    env = os.environ.get("RAILTRACKS_HOME")
    if env:
        return Path(env) / _DIRNAME

    current = Path.cwd()
    for directory in [current, *current.parents]:
        candidate = directory / _DIRNAME
        if candidate.is_dir():
            return candidate

    fallback = current / _DIRNAME
    warnings.warn(
        f"No {_DIRNAME!r} directory found in '{current}' or any parent directory. "
        f"Data will be written to '{fallback}'. "
        f"Run 'railtracks init' from your project root to set a permanent location.",
        UserWarning,
        stacklevel=2,
    )
    return fallback
