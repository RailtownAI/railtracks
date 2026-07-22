from __future__ import annotations

import contextvars
import logging
import uuid
import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Coroutine, KeysView

from railtracks.exceptions import ContextError

if TYPE_CHECKING:
    from railtracks.pubsub.publisher import RTPublisher

from railtracks.utils.config import ExecutorConfig

from .external import ExternalContext, MutableExternalContext
from .scope_link import ScopeLink
from .session_context import ScopeEntry, ScopeKind, SessionContext


class RunnerContextVars:
    """
    A class to hold context variables which are scoped within the context of a single runner.
    """

    def __init__(
        self,
        *,
        session_context: SessionContext,
        external_context: ExternalContext,
    ):
        self.session_context = session_context
        self.external_context = external_context


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
    return context is not None and context.session_context.is_active


def get_publisher() -> RTPublisher:
    """
    Get the publisher for the current thread's global variables.

    Returns:
        RTPublisher: The publisher associated with the current thread's global variables.

    Raises:
        RuntimeError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.session_context.publisher


def get_session_id() -> str | None:
    """
    Get the runner ID of the current thread's global variables.

    Returns:
        str: The runner ID associated with the current thread's global variables.

    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.session_context.session_id


def get_parent_id() -> str | None:
    """
    Get the id of the currently active node (walks up the scope chain to the
    nearest node/node-body entry).

    Returns:
        str | None: The parent ID associated with the current thread's global variables, or None if not set.

    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.session_context.current_node_id


def get_middleware_id() -> str | None:
    """
    Get the id of the currently active middleware invocation (walks up the
    scope chain to the nearest middleware entry).

    Returns:
        str | None: The middleware id, or None if no middleware is currently active.

    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.session_context.current_middleware_id


def get_run_id() -> str | None:
    """
    Get the run ID of the current thread's global variables.

    Returns:
        str | None: The run ID associated with the current thread's global variables, or None if not set.


    Raises:
        ContextError: If the global variables have not been registered.
    """
    context = safe_get_runner_context()
    return context.session_context.run_id


def get_current_scope() -> ScopeLink[ScopeEntry] | None:
    """Get the current thread's full scope chain."""
    context = safe_get_runner_context()
    return context.session_context.scope


@contextmanager
def restore_scope(scope: ScopeLink[ScopeEntry] | None, run_id: str | None):
    """Replaces (not pushes onto) the ambient scope chain + run_id, reverting on exit."""
    ctx = safe_get_runner_context()
    new_session_context = SessionContext(
        session_id=ctx.session_context.session_id,
        run_id=run_id if run_id is not None else ctx.session_context.run_id,
        publisher=ctx.session_context.publisher,
        scope=scope,
        executor_config=ctx.session_context.executor_config,
    )
    new_ctx = RunnerContextVars(
        session_context=new_session_context,
        external_context=ctx.external_context,
    )
    token = runner_context.set(new_ctx)
    try:
        yield
    finally:
        runner_context.reset(token)


def register_globals(
    *,
    session_id: str,
    rt_publisher: RTPublisher | None,
    executor_config: ExecutorConfig,
    global_context_vars: dict[str, Any],
):
    """
    Register the global variables for the current thread.
    """
    s_c = SessionContext(
        publisher=rt_publisher,
        session_id=session_id,
        executor_config=executor_config,
    )
    e_c = MutableExternalContext(global_context_vars)

    runner_context_vars = RunnerContextVars(
        session_context=s_c,
        external_context=e_c,
    )

    runner_context.set(runner_context_vars)


async def activate_publisher():
    """
    Activate the publisher for the current thread's global variables.

    This function should be called to ensure that the publisher is running and can be used to publish messages.
    """
    r_c = safe_get_runner_context()
    session_context = r_c.session_context
    assert session_context is not None

    assert session_context.publisher is not None

    await session_context.publisher.start()


async def shutdown_publisher():
    """
    Shutdown the publisher for the current thread's global variables.

    This function should be called to stop the publisher and clean up resources.
    """
    context = safe_get_runner_context()
    context = context.session_context
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

    return context.session_context.executor_config


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


def _push_scope(entry: ScopeEntry, *, run_id: str | None = None) -> contextvars.Token:
    """Pushes `entry` onto the scope chain, returning the token needed to revert it."""
    ctx = safe_get_runner_context()
    new_session_context = ctx.session_context.with_scope_pushed(entry, run_id=run_id)
    new_ctx = RunnerContextVars(
        session_context=new_session_context,
        external_context=ctx.external_context,
    )
    return runner_context.set(new_ctx)


class ContextVarScopeManager:
    """ScopeManager backed by the `runner_context` ContextVar."""

    @contextmanager
    def enter_node(self, node_id: str):
        
        ctx = safe_get_runner_context()
        established_run_id = (
            ctx.session_context.run_id
            if ctx.session_context.run_id is not None
            else node_id
        )
        token = _push_scope(
            ScopeEntry(ScopeKind.NODE, node_id), run_id=established_run_id
        )
        try:
            yield
        finally:
            runner_context.reset(token)

    @contextmanager
    def enter_node_body(self):
        ctx = safe_get_runner_context()
        node_id = ctx.session_context.current_node_id
        if node_id is None:
            raise RuntimeError(
                "Cannot enter a node-body scope outside of an active node scope"
            )
        assert node_id is not None, (
            "Cannot enter a node-body scope outside of an active node scope"
        )
        token = _push_scope(ScopeEntry(ScopeKind.NODE_BODY, node_id.id))
        try:
            yield
        finally:
            runner_context.reset(token)

    @contextmanager
    def enter_middleware(self, name: str):
        middleware_id = str(uuid.uuid4())
        token = _push_scope(ScopeEntry(ScopeKind.MIDDLEWARE, middleware_id, name=name))
        try:
            yield middleware_id
        finally:
            runner_context.reset(token)


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

    new_config = config.precedence_overwritten(
        timeout=timeout,
        end_on_error=end_on_error,
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
            middleware_id = get_middleware_id()

        except ContextError:
            parent_id = None
            run_id = None
            session_id = None
            middleware_id = None

        new_variables = {
            "node_id": parent_id,
            "run_id": run_id,
            "session_id": session_id,
            "middleware_id": middleware_id,
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
