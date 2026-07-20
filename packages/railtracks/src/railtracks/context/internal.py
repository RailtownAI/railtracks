from __future__ import annotations

from typing import TYPE_CHECKING

from railtracks.utils.config import ExecutorConfig

if TYPE_CHECKING:
    from railtracks.pubsub.publisher import RTPublisher


class InternalContext:
    """
    The InternalContext class is used to store global variables designed to be used in the RT system.

    The tooling in the class is very tightly dependent on the requirements of the RT system.
    """

    def __init__(
        self,
        *,
        session_id: str,
        run_id: str | None = None,
        publisher: RTPublisher | None = None,
        parent_id: str | None = None,
        executor_config: ExecutorConfig,
        stream_enabled: bool = False,
        stream_id: str | None = None,
    ):
        self._parent_id: str | None = parent_id
        self._publisher: RTPublisher | None = publisher
        self._session_id: str = session_id
        self._run_id: str | None = run_id
        self._executor_config: ExecutorConfig = executor_config
        self._stream_enabled: bool = stream_enabled
        self._stream_id: str | None = stream_id

    @property
    def executor_config(self) -> ExecutorConfig:
        """
        Returns the executor configuration for this run.
        """
        return self._executor_config

    @executor_config.setter
    def executor_config(self, value: ExecutorConfig):
        """
        Sets the executor configuration for this run.
        """
        self._executor_config = value

    # Not super pythonic but it allows us to slap in debug statements on the getters and setters with ease
    @property
    def parent_id(self):
        return self._parent_id

    @property
    def is_active(self) -> bool:
        """
        Check if the internal context has been defined.
        """
        if self._publisher is None:
            return False

        return self._publisher.is_running()

    @parent_id.setter
    def parent_id(self, value: str):
        self._parent_id = value

    @property
    def publisher(self):
        return self._publisher

    @publisher.setter
    def publisher(self, value: RTPublisher):
        self._publisher = value

    @property
    def session_id(self) -> str:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str):
        self._session_id = value

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def stream_enabled(self) -> bool:
        """True when the frame attached to this context should stream its LLM responses.

        This flag is frame-local: it is set only on the entry frame of a streamed invocation
        (see `rt.astream`) and is never inherited by child frames.
        """
        return self._stream_enabled

    @property
    def stream_id(self) -> str | None:
        """The stream scope this frame belongs to (the entry request id of a streamed run).

        Unlike `stream_enabled`, this id is inherited by child frames so their explicit
        broadcasts can be routed back to the consumer attached to the entry frame.
        """
        return self._stream_id

    def prepare_new(
        self,
        new_parent_id: str,
        run_id: str | None = None,
        stream: bool = False,
        stream_id: str | None = None,
    ) -> InternalContext:
        """
        Prepares a new InternalContext with a new parent ID. If `run_id` or `session_id` are not provided, they will default to the current context's values.

        Note: the previous publisher will copied by reference into the next object.

        Args:
            new_parent_id: The parent id of the new frame.
            run_id: The run id of the new frame. Defaults to the current context's run id.
            stream: Whether the new frame should have streaming enabled. Note this is
                deliberately NOT inherited from the current context (streaming is frame-local).
            stream_id: The stream scope id of the new frame. If None, the current context's
                stream id is inherited (so nested broadcasts stay routed to the entry consumer).
        """

        unwrapped_run_id: str | None
        if run_id is None:
            unwrapped_run_id = self._run_id
        else:
            unwrapped_run_id = run_id

        return InternalContext(
            publisher=self._publisher,
            parent_id=new_parent_id,
            session_id=self._session_id,
            run_id=unwrapped_run_id,
            executor_config=self._executor_config,
            stream_enabled=stream,
            stream_id=stream_id if stream_id is not None else self._stream_id,
        )
