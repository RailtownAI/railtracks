from __future__ import annotations

from enum import Enum
from typing import Callable

import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.utils.logging.create import get_rt_logger

from ._base import ToolSet

logger = get_rt_logger(__name__)


class State(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_LONGER_PLANNED = "no_longer_planned"


class ToDo(BaseModel):
    short_description: str = Field(description="...")
    description: str = Field(description="...")
    state: State = Field(description="...", default=State.NOT_STARTED)

    @property
    def identifier(self) -> int:
        return id(self)

    def update_state(self, new_state: State):
        self.state = new_state

    def complete_print(self) -> str:
        return f"({self.identifier}) [{self.state.value}] {self.short_description}: {self.description}"

    def simplified_print(self) -> str:
        return f"{self.state.value} - {self.short_description}"


class ToDoToolSet(ToolSet):
    def __init__(self, callback: Callable[[str, str, State], None] | None = None):
        self.todos: list[ToDo] = []

        if callback is None:

            def default_add_callback(
                short_description: str, description: str, state: State
            ):
                pass

            callback = default_add_callback

        self.add_callback = callback

    def add(
        self, short_description: str, description: str, state: State = State.NOT_STARTED
    ):
        """Add a new todo to this toolset instance.

        Args:
            short_description: Brief, unique label for the todo (used as its identifier in listings).
            description: Full details of what needs to be done.
            state: Initial state of the todo. Defaults to NOT_STARTED.

        Raises:
            ValueError: If a todo with the same short_description or description already exists.
        """
        to_do = ToDo(
            short_description=short_description, description=description, state=state
        )
        validity_check = self.check_if_valid(self.todos, to_do)
        if validity_check is not None:
            raise ValueError(validity_check)

        try:
            self.add_callback(short_description, description, state)
        except Exception as e:
            logger.error(f"Error in callback for todo: {e}")

        self.todos.append(to_do)

    @classmethod
    def check_if_valid(cls, todos: list[ToDo], todo_to_add: ToDo) -> str | None:
        if todo_to_add.short_description in [todo.short_description for todo in todos]:
            return f"Todo with short description '{todo_to_add.short_description}' already exists. Please provide a unique short description."

        if todo_to_add.description in [todo.description for todo in todos]:
            return f"Todo with description '{todo_to_add.description}' already exists. Please provide a unique description."

        if todo_to_add.identifier in [todo.identifier for todo in todos]:
            raise ValueError(
                f"Todo with identifier '{todo_to_add.identifier}' already exists. Please provide a unique identifier."
            )

        return None

    def _get_all_todos(self) -> list[ToDo]:
        """Return all todos for this toolset instance.

        Returns:
            List of all ToDo objects tracked by this instance.
        """
        return self.todos

    def get_all_todos(self) -> list[str]:
        """Return formatted strings for all active todos (excludes NO_LONGER_PLANNED).

        Returns:
            List of complete_print() strings for todos not in NO_LONGER_PLANNED state.
        """
        return [
            todo.complete_print()
            for todo in self._get_all_todos()
            if todo.state != State.NO_LONGER_PLANNED
        ]

    def get_completed_todos(self) -> list[str]:
        """Return formatted strings for all completed todos in this instance.

        Returns:
            List of complete_print() strings for todos in COMPLETED state.
        """
        return [
            todo.complete_print()
            for todo in self._get_all_todos()
            if todo.state == State.COMPLETED
        ]

    def get_not_started_todos(self) -> list[str]:
        """Return formatted strings for todos that have not been started in this instance.

        Returns:
            List of complete_print() strings for todos in NOT_STARTED state.
        """
        return [
            todo.complete_print()
            for todo in self._get_all_todos()
            if todo.state == State.NOT_STARTED
        ]

    def get_incomplete_todos(self) -> list[str]:
        """Return formatted strings for all unfinished todos (not started, in progress, or failed).

        NO_LONGER_PLANNED todos are excluded.

        Returns:
            List of complete_print() strings for todos in NOT_STARTED, IN_PROGRESS, or FAILED state.
        """
        incomplete_states = {State.NOT_STARTED, State.IN_PROGRESS, State.FAILED}
        return [
            todo.complete_print()
            for todo in self._get_all_todos()
            if todo.state in incomplete_states
        ]

    def get_failed_todos(self) -> list[str]:
        """Return formatted strings for all failed todos in this instance.

        Returns:
            List of complete_print() strings for todos in FAILED state.
        """
        return [
            todo.complete_print()
            for todo in self._get_all_todos()
            if todo.state == State.FAILED
        ]

    def complete_todo_by_id(self, todo_id: int):
        """Mark a todo as COMPLETED.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in this instance.
        """
        for todo in self._get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(State.COMPLETED)
                return "Successfully completed todo:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def start_todo_by_id(self, todo_id: int):
        """Mark a todo as IN_PROGRESS.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in this instance.
        """
        for todo in self._get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(State.IN_PROGRESS)
                return "Successfully started todo:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def fail_todo_by_id(self, todo_id: int):
        """Mark a todo as FAILED.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in this instance.
        """
        for todo in self._get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(State.FAILED)
                return "Successfully marked todo as failed:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def no_longer_plan_todo_by_id(self, todo_id: int):
        """Mark a todo as NO_LONGER_PLANNED.

        Todos in this state are excluded from most views. Use when a planned task
        is no longer relevant without it being a failure.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in this instance.
        """
        for todo in self._get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(State.NO_LONGER_PLANNED)
                return "Successfully marked todo as no longer planned:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def make_all_no_longer_planned(self):
        """Mark all not-started and in-progress todos as NO_LONGER_PLANNED.

        COMPLETED and FAILED todos are left unchanged. Use when abandoning the
        current plan entirely.

        Returns:
            Confirmation string with the number of todos affected.
        """
        affected = 0
        for todo in self._get_all_todos():
            if todo.state in {State.NOT_STARTED, State.IN_PROGRESS}:
                todo.update_state(State.NO_LONGER_PLANNED)
                affected += 1
        return f"Marked {affected} todo(s) as no longer planned."

    def update_todo_by_id(self, todo_id: int, new_state: State):
        """Update a todo to an arbitrary state.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).
            new_state: The target State to transition the todo to.

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in this instance.
        """
        for todo in self._get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(new_state)
                return "Successfully updated todo:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def pretty_dashboard(self) -> str:
        """Return a human-readable summary of active todos (excludes NO_LONGER_PLANNED).

        Returns:
            Formatted string listing each active todo's state and short description, or a
            'No todos found.' message if none exist.
        """
        todos = [t for t in self._get_all_todos() if t.state != State.NO_LONGER_PLANNED]
        if not todos:
            return "No todos found."

        dashboard_str = "To-Dos\n"
        for todo in todos:
            dashboard_str += todo.simplified_print() + "\n"

        return dashboard_str.strip()

    @classmethod
    def prompt(cls) -> str:
        return (
            "Use the todo tools to plan and track your work. "
            "Begin by calling add() for every task before starting any of them. "
            "Call start_todo_by_id() when you begin a task and complete_todo_by_id() when it is done. "
            "If a task cannot be completed, call fail_todo_by_id() instead. "
            "If a planned task is no longer relevant, call no_longer_plan_todo_by_id() to remove it from active views. "
            "To abandon the entire current plan, call make_all_no_longer_planned() — this leaves completed and failed todos unchanged. "
            "Use update_todo_by_id() if a task needs a state change outside of the helpers above. "
            "Retrieve identifiers via get_all_todos() before calling any id-based method. "
            "Each todo requires a unique short_description and description."
        )

    def tool_set(self) -> list[RTFunction]:
        functions = [
            self.add,
            self.complete_todo_by_id,
            self.start_todo_by_id,
            self.fail_todo_by_id,
            self.no_longer_plan_todo_by_id,
            self.make_all_no_longer_planned,
            self.update_todo_by_id,
            self.get_all_todos,
            self.get_completed_todos,
            self.get_not_started_todos,
            self.get_incomplete_todos,
            self.get_failed_todos,
        ]

        return [rt.function_node(func) for func in functions]
