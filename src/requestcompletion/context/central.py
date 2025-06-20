from __future__ import annotations

import contextvars
import warnings
from typing import Any, Callable


from requestcompletion.context.external import ImmutableExternalContext, ExternalContext


from requestcompletion.config import ExecutorConfig
from requestcompletion.context.internal import InternalContext
from requestcompletion.pubsub.publisher import RCPublisher

external_context: contextvars.ContextVar[ExternalContext] = contextvars.ContextVar(
    "external_context", default=ImmutableExternalContext()
)
config: contextvars.ContextVar[ExecutorConfig | None] = contextvars.ContextVar(
    "executor_config", default=ExecutorConfig()
)
thread_context: contextvars.ContextVar[InternalContext | None] = contextvars.ContextVar(
    "thread_context", default=None
)


def get_globals() -> InternalContext:
    """
    Get the global variables for the current thread.
    """
    return thread_context.get()


def is_context_present():
    t_c = thread_context.get()
    return t_c is not None


def is_context_active():
    """
    Check if the global variables for the current thread are active.

    Returns:
        bool: True if the global variables are active, False otherwise.
    """
    context = thread_context.get()
    return context is not None and context.is_active


def get_publisher() -> RCPublisher:
    """
    Get the publisher for the current thread's global variables.

    Returns:
        RCPublisher: The publisher associated with the current thread's global variables.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = thread_context.get()
    if context is None:
        raise RuntimeError(
            "Global variables have not been registered. Call `register_globals()` first."
        )
    return context.publisher


def get_runner_id() -> str:
    """
    Get the runner ID of the current thread's global variables.

    Returns:
        str: The runner ID associated with the current thread's global variables.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = thread_context.get()
    if context is None:
        raise RuntimeError(
            "Global variables have not been registered. Call `register_globals()` first."
        )
    return context.runner_id


def get_parent_id() -> str | None:
    """
    Get the parent ID of the current thread's global variables.

    Returns:
        str | None: The parent ID associated with the current thread's global variables, or None if not set.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = thread_context.get()
    if context is None:
        raise RuntimeError(
            "Global variables have not been registered. Call `register_globals()` first."
        )
    return context.parent_id


def register_globals(
    runner_id: str,
    rc_publisher: RCPublisher | None = None,
    parent_id: str | None = None,
):
    """
    Register the global variables for the current thread.
    """
    i_c = InternalContext(
        publisher=rc_publisher, parent_id=parent_id, runner_id=runner_id
    )
    thread_context.set(i_c)


async def activate_publisher():
    """
    Activate the publisher for the current thread's global variables.

    This function should be called to ensure that the publisher is running and can be used to publish messages.
    """
    context = thread_context.get()
    assert context is not None

    assert context.publisher is not None

    await context.publisher.start()


async def shutdown_publisher():
    """
    Shutdown the publisher for the current thread's global variables.

    This function should be called to stop the publisher and clean up resources.
    """
    context = thread_context.get()
    assert context is not None

    assert context.publisher.is_running()
    await context.publisher.shutdown()


def get_config() -> ExecutorConfig | None:
    """
    Get the executor configuration for the current thread's global variables.

    Returns:
        ExecutorConfig | None: The executor configuration associated with the current thread's global variables, or None if not set.
    """
    return config.get()


def set_global_config(
    executor_config: ExecutorConfig,
):
    """
    Set the executor configuration for the current thread's global variables.

    Args:
        executor_config (ExecutorConfig): The executor configuration to set.
    """
    config.set(executor_config)


def update_parent_id(new_parent_id: str):
    """
    Update the parent ID of the current thread's global variables.
    """
    current_context = thread_context.get()

    if current_context is None:
        raise RuntimeError("No global variable set")

    new_context = current_context.prepare_new(new_parent_id)

    thread_context.set(new_context)


def delete_globals():
    thread_context.set(None)


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
    context = external_context.get()
    return context.get(key, default=default)


def put(
    key: str,
    value: Any,
):
    """
    Set a value in the external context.

    :param key: The key to set.
    :param value: The value to associate with the key.
    """
    context = external_context.get()
    context.put(key, value)


def set_config(executor_config: ExecutorConfig):
    """
    Sets the executor config for the current runner.
    """

    if is_context_active():
        warnings.warn(
            "The executor config is being set after the runner has been created, this is not recomended"
        )
        # TODO figure out what happens when you do this.

    config.set(executor_config)


def set_streamer(subscriber: Callable[[str], None]):
    """
    Sets the data streamer for the current runner.
    """

    if is_context_active():
        warnings.warn(
            "The data streamer is being set after the runner has been created, this is not recomended"
        )
        # TODO figure out what happens when you do this.

    executor_config = config.get()
    executor_config.subscriber = subscriber
    config.set(executor_config)
