from __future__ import annotations

import contextvars
import logging
import os
import warnings
from typing import TYPE_CHECKING, Any, Callable, Coroutine, KeysView

from railtracks.exceptions import ContextError

if TYPE_CHECKING:
    from railtracks.pubsub.publisher import RTPublisher

from railtracks.utils.config import ExecutorConfig
from railtracks.utils.logging.config import AllowableLogLevels

from ..utils.logging.config import configure_module_logging
from .external import ExternalContext, MutableExternalContext
from .internal import InternalContext


class RunnerContextVars:
    """
    A class to hold context variables which are scoped within the context of a single runner.
    """

    def __init__(
        self,
        *,
        internal_context: InternalContext,
        external_context: ExternalContext,
    ):
        self.internal_context = internal_context
        self.external_context = external_context

    def prepare_new(self, new_parent_id: str, new_run_id: str | None = None):
        """
        Update the parent ID of the internal context.
        """
        new_internal_context = self.internal_context.prepare_new(
            new_parent_id=new_parent_id,
            run_id=new_run_id,
        )

        return RunnerContextVars(
            internal_context=new_internal_context,
            external_context=self.external_context,
        )


runner_context: contextvars.ContextVar[RunnerContextVars | None] = (
    contextvars.ContextVar("runner_context", default=None)
)

global_executor_config: contextvars.ContextVar[ExecutorConfig] = contextvars.ContextVar(
    "executor_config", default=ExecutorConfig()
)


def safe_get_runner_context() -> RunnerContextVars:
    """
    Safely get the runner context for the current thread.

        Returns:
            RunnerContextVars: The runner context associated with the current thread.

        Raises:
            ContextError: If the global variables have not been registered.
    """
    context = runner_context.get()
    if context is None:
        raise ContextError(
            message="Context is not available. But some function tried to access it.",
            notes=[
                "You need to have an active runner to access context.",
                "Eg.-\n with rt.Session():\n    _ = rt.call(node)",
            ],
        )
    return context


def is_context_present():
    """Returns true if a context exists."""
    t_c = runner_context.get()
    return t_c is not None


def is_context_active():
    """
    Check if the global variables for the current thread are active.

    Returns:
        bool: True if the global variables are active, False otherwise.
    """
    context = runner_context.get()
    return context is not None and context.internal_context.is_active


def get_publisher() -> RTPublisher:
    """
    Get the publisher for the current thread's global variables.

    Returns:
        RTPublisher: The publisher associated with the current thread's global variables.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.internal_context.publisher


def get_session_id() -> str | None:
    """
    Get the runner ID of the current thread's global variables.

    Returns:
        str: The runner ID associated with the current thread's global variables.

    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.internal_context.session_id


def get_parent_id() -> str | None:
    """
    Get the parent ID of the current thread's global variables.

    Returns:
        str | None: The parent ID associated with the current thread's global variables, or None if not set.

    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.internal_context.parent_id


def get_run_id() -> str | None:
    """
    Get the run ID of the current thread's global variables.

    Returns:
        str | None: The run ID associated with the current thread's global variables, or None if not set.


    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.internal_context.run_id


def register_globals(
    *,
    session_id: str,
    rt_publisher: RTPublisher | None,
    parent_id: str | None,
    executor_config: ExecutorConfig,
    global_context_vars: dict[str, Any],
):
    """
    Register the global variables for the current thread.
    """
    i_c = InternalContext(
        publisher=rt_publisher,
        parent_id=parent_id,
        session_id=session_id,
        executor_config=executor_config,
    )
    e_c = MutableExternalContext(global_context_vars)

    runner_context_vars = RunnerContextVars(
        internal_context=i_c,
        external_context=e_c,
    )

    runner_context.set(runner_context_vars)


async def activate_publisher():
    """
    Activate the publisher for the current thread's global variables.

    This function should be called to ensure that the publisher is running and can be used to publish messages.
    """
    r_c = safe_get_runner_context()
    internal_context = r_c.internal_context
    assert internal_context is not None

    assert internal_context.publisher is not None

    await internal_context.publisher.start()


async def shutdown_publisher():
    """
    Shutdown the publisher for the current thread's global variables.

    This function should be called to stop the publisher and clean up resources.
    """
    context = safe_get_runner_context()
    context = context.internal_context
    assert context is not None

    assert context.publisher.is_running()
    await context.publisher.shutdown()


def get_global_config() -> ExecutorConfig:
    """
    Get the executor configuration for the current thread's global variables.

    Returns:
        ExecutorConfig: The executor configuration associated with the current thread's global variables, or None if not set.
    """
    executor_config = global_executor_config.get()
    return executor_config


def get_local_config() -> ExecutorConfig:
    """
    Get the executor configuration for the current thread's global variables.

    Returns:
        ExecutorConfig: The executor configuration associated with the current thread's global variables, or None if not set.
    """
    context = safe_get_runner_context()

    return context.internal_context.executor_config


def set_local_config(
    executor_config: ExecutorConfig,
):
    """
    Set the executor configuration for the current thread's global variables.

    Args:
        executor_config (ExecutorConfig): The executor configuration to set.
    """
    context = safe_get_runner_context()

    context.executor_config = executor_config
    runner_context.set(context)


def set_global_config(
    executor_config: ExecutorConfig,
):
    """
    Set the executor configuration for the current thread's global variables.

    Args:
        executor_config (ExecutorConfig): The executor configuration to set.
    """
    global_executor_config.set(executor_config)


def update_parent_id(new_parent_id: str, new_run_id: str | None = None):
    """
    Update the parent ID of the current thread's global variables.

    If no run ID is provided, the current run ID will be used.
    """
    current_context = safe_get_runner_context()

    assert (
        new_run_id is not None or current_context.internal_context.run_id is not None
    ), "You cannot update the parent ID while a run ID is inactive"

    if current_context is None:
        raise RuntimeError("No global variable set")

    new_context = current_context.prepare_new(new_parent_id, new_run_id=new_run_id)

    runner_context.set(new_context)


def delete_globals():
    """Resets the globals to None."""
    runner_context.set(None)


def get(
    key: str,
    /,
    default: Any | None = None,
):
    """
    Get a value from context

    Args:
        key (str): The key to retrieve.
        default (Any | None): The default value to return if the key does not exist. If set to None and the key does not exist, a KeyError will be raised.
    Returns:
        Any: The value associated with the key, or the default value if the key does not exist.

    Raises:
        KeyError: If the key does not exist and no default value is provided.
    """
    context = safe_get_runner_context()
    return context.external_context.get(key, default=default)


def put(
    key: str,
    value: Any,
):
    """
    Set a value in the context.

    Args:
        key (str): The key to set.
        value (Any): The value to set.
    """
    context = safe_get_runner_context()
    context.external_context.put(key, value)


def update(data: dict[str, Any]):
    """
    Sets the values in the context. If the context already has values, this will overwrite them, but it will not delete any existing keys.

    Args:
        data (dict[str, Any]): The data to update the context with.
    """
    context = safe_get_runner_context()
    context.external_context.update(data)


def delete(key: str):
    """
    Delete a key from the context.

    Args:
        key (str): The key to delete.

    Raises:
        KeyError: If the key does not exist.
    """
    context = safe_get_runner_context()
    context.external_context.delete(key)


def keys() -> KeysView[str]:
    """
    Get the keys of the context.

    Returns:
        KeysView[str]: The keys in the context.
    """
    context = safe_get_runner_context()
    return context.external_context.keys()


def set_config(
    *,
    timeout: float | None = None,
    end_on_error: bool | None = None,
    logging_setting: AllowableLogLevels | None = None,
    log_file: str | os.PathLike | None = None,
    broadcast_callback: (
        Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
    ) = None,
    prompt_injection: bool | None = None,
    save_state: bool | None = None,
):
    """
    Sets the global configuration for the executor. This will be propagated to all new runners created after this call.

    - If you call this function after the runner has been created, it will not affect the current runner.
    - This function will only overwrite the values that are provided, leaving the rest unchanged.


    """

    if is_context_active():
        warnings.warn(
            "The executor config is being set after the runner has been created, this is not recommended"
        )

    config = global_executor_config.get()

    if logging_setting or log_file:
        # default will be set at module import time, this is for overwrites
        configure_module_logging(level=logging_setting, log_file=log_file)

    new_config = config.precedence_overwritten(
        timeout=timeout,
        end_on_error=end_on_error,
        logging_setting=logging_setting,
        log_file=log_file,
        subscriber=broadcast_callback,
        prompt_injection=prompt_injection,
        save_state=save_state,
    )

    global_executor_config.set(new_config)


class RTContextLoggingAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        try:
            parent_id = get_parent_id()
            run_id = get_run_id()
            session_id = get_session_id()

        except ContextError:
            parent_id = None
            run_id = None
            session_id = None

        new_variables = {
            "node_id": parent_id,
            "run_id": run_id,
            "session_id": session_id,
        }

        kwargs["extra"] = {**kwargs.get("extra", {}), **new_variables}

        return msg, kwargs


def session_id():
    """
    Gets the current session ID if it exists, otherwise returns None.
    """
    try:
        return get_session_id()
    except ContextError:
        return None
