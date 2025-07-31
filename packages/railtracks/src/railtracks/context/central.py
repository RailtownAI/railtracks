from __future__ import annotations

import contextvars
import os
import warnings
from typing import Any, Callable, Coroutine

from railtracks.exceptions import ContextError
from railtracks.pubsub.publisher import RTPublisher
from railtracks.utils.config import ExecutorConfig
from railtracks.utils.logging.config import allowable_log_levels

from .external import ExternalContext, MutableExternalContext
from .internal import InternalContext


class RunnerContextVars:
    """
    A class to hold context variables which are scoped within the context of a single runner.
    """

    def __init__(
        self,
        *,
        runner_id: str,
        internal_context: InternalContext,
        external_context: ExternalContext,
    ):
        self.runner_id = runner_id
        self.internal_context = internal_context
        self.external_context = external_context

    def prepare_new(self, new_parent_id: str):
        """
        Update the parent ID of the internal context.
        """
        new_internal_context = self.internal_context.prepare_new(new_parent_id)

        return RunnerContextVars(
            runner_id=self.runner_id,
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
            RuntimeError: If the global variables have not been registered.
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


def get_runner_id() -> str:
    """
    Get the runner ID of the current thread's global variables.

    Returns:
        str: The runner ID associated with the current thread's global variables.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.runner_id


def get_parent_id() -> str | None:
    """
    Get the parent ID of the current thread's global variables.

    Returns:
        str | None: The parent ID associated with the current thread's global variables, or None if not set.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.internal_context.parent_id


def register_globals(
    *,
    runner_id: str,
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
        runner_id=runner_id,
        executor_config=executor_config,
    )
    e_c = MutableExternalContext(global_context_vars)

    runner_context_vars = RunnerContextVars(
        runner_id=runner_id,
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


def update_parent_id(new_parent_id: str):
    """
    Update the parent ID of the current thread's global variables.
    """
    current_context = safe_get_runner_context()

    if current_context is None:
        raise RuntimeError("No global variable set")

    new_context = current_context.prepare_new(new_parent_id)

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
    Get a value from the context object

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
    Set a value in the external context.

    :param key: The key to set.
    :param value: The value to associate with the key.
    """
    context = safe_get_runner_context()
    context.external_context.put(key, value)


def set_config(
    *,
    timeout: float | None = None,
    end_on_error: bool | None = None,
    logging_setting: allowable_log_levels | None = None,
    log_file: str | os.PathLike | None = None,
    broadcast_callback: (
        Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
    ) = None,
    run_identifier: str | None = None,
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
            "The executor config is being set after the runner has been created, this is not recomended"
        )

    config = global_executor_config.get()
    new_config = config.precedence_overwritten(
        timeout=timeout,
        end_on_error=end_on_error,
        logging_setting=logging_setting,
        log_file=log_file,
        subscriber=broadcast_callback,
        run_identifier=run_identifier,
        prompt_injection=prompt_injection,
        save_state=save_state,
    )

    global_executor_config.set(new_config)
