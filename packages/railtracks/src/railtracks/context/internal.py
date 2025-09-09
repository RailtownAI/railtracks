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
    ):
        self._parent_id: str | None = parent_id
        self._publisher: RTPublisher | None = publisher
        self._session_id: str = session_id
        self._run_id: str | None = run_id
        self._executor_config: ExecutorConfig = executor_config

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

    def prepare_new(
        self, new_parent_id: str, run_id: str | None = None
    ) -> InternalContext:
        """
        Prepares a new InternalContext with a new parent ID. If `run_id` or `session_id` are not provided, they will default to the current context's values.

        Note: the previous publisher will copied by reference into the next object.

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
        )
