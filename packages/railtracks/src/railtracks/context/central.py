from __future__ import annotations

import contextvars
import logging
import warnings
from typing import TYPE_CHECKING, Any, Callable, KeysView

from railtracks.exceptions import ContextError

if TYPE_CHECKING:
    from railtracks.pubsub.publisher import RTPublisher

from railtracks.utils.config import ExecutorConfig

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

    def prepare_new(
        self,
        new_parent_id: str,
        new_run_id: str | None = None,
        stream: bool = False,
        stream_id: str | None = None,
    ):
        """
        Update the parent ID of the internal context.

        `stream` marks the new frame as streaming-enabled (frame-local, never inherited),
        while `stream_id` (inherited when None) tracks which stream scope the frame belongs to.
        """
        new_internal_context = self.internal_context.prepare_new(
            new_parent_id=new_parent_id,
            run_id=new_run_id,
            stream=stream,
            stream_id=stream_id,
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
        ContextError: If the global variables have not been registered or no publisher is
            attached to the current context.
    """
    context = safe_get_runner_context()
    publisher = context.internal_context.publisher
    if publisher is None:
        raise ContextError(
            message="No publisher is attached to the current context.",
            notes=[
                "You need to have an active runner to access the publisher.",
                "Eg.-\n with rt.Session():\n    _ = rt.call(node)",
            ],
        )
    return publisher


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


def is_streaming_enabled() -> bool:
    """
    Returns True when the current frame was invoked with streaming enabled (via `rt.astream`
    / `Flow.astream` — callbacks never enable streaming).

    LLM nodes use this to decide whether to stream their model responses token-by-token.
    The flag is frame-local: it is True only for the entry frame of a streamed invocation and
    never propagates to nested `rt.call` children. Returns False when no context is present.
    """
    context = runner_context.get()
    if context is None:
        return False
    return context.internal_context.stream_enabled


def get_stream_id() -> str | None:
    """
    Returns the stream scope id of the current frame (the entry request id of the streamed
    run this frame belongs to), or None when the frame is not part of a streamed run or no
    context is present.
    """
    context = runner_context.get()
    if context is None:
        return None
    return context.internal_context.stream_id


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
    internal_context = context.internal_context

    publisher = internal_context.publisher
    assert publisher is not None, "Cannot shutdown a publisher that was never attached."
    assert publisher.is_running()
    await publisher.shutdown()


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

    # the config lives on the internal context (RunnerContextVars has no such attribute)
    context.internal_context.executor_config = executor_config
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


def update_parent_id(
    new_parent_id: str,
    new_run_id: str | None = None,
    *,
    stream: bool = False,
    stream_id: str | None = None,
):
    """
    Update the parent ID of the current thread's global variables.

    If no run ID is provided, the current run ID will be used.

    Args:
        new_parent_id: The parent id of the new frame.
        new_run_id: The run id of the new frame (defaults to the current one).
        stream: If True, the new frame will have streaming enabled. This is frame-local:
            child frames created afterwards will NOT inherit it.
        stream_id: The stream scope id for the new frame. If None, the current stream id is
            inherited.
    """
    current_context = safe_get_runner_context()

    assert (
        new_run_id is not None or current_context.internal_context.run_id is not None
    ), "You cannot update the parent ID while a run ID is inactive"

    if current_context is None:
        raise RuntimeError("No global variable set")

    new_context = current_context.prepare_new(
        new_parent_id, new_run_id=new_run_id, stream=stream, stream_id=stream_id
    )

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
    broadcast_callback: (
        Callable[[str], Any] | dict[str, Callable[[str], Any]] | None
    ) = None,
    prompt_injection: bool | None = None,
    save_state: bool | None = None,
):
    """
    Sets the global configuration for the executor. This will be propagated to all new runners created after this call.

    - If you call this function after the runner has been created, it will not affect the current runner.
    - This function will only overwrite the values that are provided, leaving the rest unchanged.

    Args:
        timeout: The maximum number of seconds to wait for a response to your top-level request.
        end_on_error: If True, the execution will stop when an exception is encountered.
        broadcast_callback: A passive listener on the broadcast bus (or a dict mapping channel
            name -> callback to route items per channel). It never enables streaming — only
            `rt.astream` / `Flow.astream` do.
        prompt_injection: If True, the prompt will be automatically injected from context variables.
        save_state: If True, the state of the execution will be saved to a file at the end of the run.
    """

    if is_context_active():
        warnings.warn(
            "The executor config is being set after the runner has been created, this is not recommended"
        )

    config = global_executor_config.get()

    new_config = config.precedence_overwritten(
        timeout=timeout,
        end_on_error=end_on_error,
        broadcast_callback=broadcast_callback,
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
