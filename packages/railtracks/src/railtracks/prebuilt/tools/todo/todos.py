from __future__ import annotations

import asyncio
from enum import Enum
from typing import Callable

import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.utils.logging.create import get_rt_logger

from .._base import ToolSet

logger = get_rt_logger(__name__)


class State(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_LONGER_PLANNED = "no_longer_planned"


class ToDo(BaseModel):
    id: int = Field(
        description="Unique integer identifier assigned by the owning ToDoToolSet."
    )
    short_description: str = Field(
        description="Brief unique label shown in todo listings."
    )
    description: str = Field(description="Full details of what needs to be done.")
    state: State = Field(
        description="Current lifecycle state of this todo.", default=State.NOT_STARTED
    )

    def update_state(self, new_state: State):
        self.state = new_state

    def complete_print(self) -> str:
        return f"({self.id}) [{self.state.value}] {self.short_description}: {self.description}"

    def simplified_print(self) -> str:
        return f"{self.state.value} - {self.short_description}"


class ToDoToolSet(ToolSet):
    def __init__(self, callback: Callable[[str, str, State], None] | None = None):
        """Create an empty toolset with an optional post-add callback.

        Args:
            callback: Invoked after each successful add() with (short_description, description, state).
                      Exceptions are logged and swallowed; the todo is always committed regardless.
        """
        self.todos: list[ToDo] = []
        self._lock = asyncio.Lock()

        if callback is None:

            def default_add_callback(
                short_description: str, description: str, state: State
            ):
                pass

            callback = default_add_callback

        self.add_callback = callback

    async def add(
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
        async with self._lock:
            to_do = ToDo(
                id=len(self.todos) + 1,
                short_description=short_description,
                description=description,
                state=state,
            )

            validity_check = self.check_if_valid(self.todos, to_do)
            if validity_check is not None:
                raise ValueError(validity_check)

            self.todos.append(to_do)

        # Callback fires after the todo is committed; kept outside the lock so
        # user-provided callbacks cannot cause a deadlock.
        try:
            self.add_callback(short_description, description, state)
        except Exception as e:
            logger.error(f"Error in callback for todo: {e}")

    @classmethod
    def check_if_valid(cls, todos: list[ToDo], todo_to_add: ToDo) -> str | None:
        """Return an error message if todo_to_add conflicts with existing todos, else None.

        Args:
            todos: The current list of todos to validate against.
            todo_to_add: The candidate todo whose short_description and description are checked.
        """
        if todo_to_add.short_description in [todo.short_description for todo in todos]:
            return f"Todo with short description '{todo_to_add.short_description}' already exists. Please provide a unique short description."

        if todo_to_add.description in [todo.description for todo in todos]:
            return f"Todo with description '{todo_to_add.description}' already exists. Please provide a unique description."

        return None

    def _get_all_todos(self) -> list[ToDo]:
        return self.todos

    async def get_all_todos(self) -> list[str]:
        """Return complete_print() strings for all active (non-NO_LONGER_PLANNED) todos."""
        async with self._lock:
            return [
                todo.complete_print()
                for todo in self._get_all_todos()
                if todo.state != State.NO_LONGER_PLANNED
            ]

    async def get_completed_todos(self) -> list[str]:
        """Return complete_print() strings for todos in COMPLETED state."""
        async with self._lock:
            return [
                todo.complete_print()
                for todo in self._get_all_todos()
                if todo.state == State.COMPLETED
            ]

    async def get_not_started_todos(self) -> list[str]:
        """Return complete_print() strings for todos in NOT_STARTED state."""
        async with self._lock:
            return [
                todo.complete_print()
                for todo in self._get_all_todos()
                if todo.state == State.NOT_STARTED
            ]

    async def get_incomplete_todos(self) -> list[str]:
        """Return complete_print() strings for todos in NOT_STARTED, IN_PROGRESS, or FAILED state."""
        incomplete_states = {State.NOT_STARTED, State.IN_PROGRESS, State.FAILED}
        async with self._lock:
            return [
                todo.complete_print()
                for todo in self._get_all_todos()
                if todo.state in incomplete_states
            ]

    async def get_failed_todos(self) -> list[str]:
        """Return complete_print() strings for todos in FAILED state."""
        async with self._lock:
            return [
                todo.complete_print()
                for todo in self._get_all_todos()
                if todo.state == State.FAILED
            ]

    async def _find_and_update(self, todo_id: int, new_state: State) -> str:
        async with self._lock:
            for todo in self._get_all_todos():
                if todo.id == todo_id:
                    todo.update_state(new_state)
                    return todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    async def complete_todo_by_id(self, todo_id: int):
        """Mark a todo as COMPLETED; raises ValueError if not found.

        Args:
            todo_id: The integer id of the todo to complete.
        """
        return "Successfully completed todo:\n" + await self._find_and_update(
            todo_id, State.COMPLETED
        )

    async def start_todo_by_id(self, todo_id: int):
        """Mark a todo as IN_PROGRESS; raises ValueError if not found.

        Args:
            todo_id: The integer id of the todo to start.
        """
        return "Successfully started todo:\n" + await self._find_and_update(
            todo_id, State.IN_PROGRESS
        )

    async def fail_todo_by_id(self, todo_id: int):
        """Mark a todo as FAILED; raises ValueError if not found.

        Args:
            todo_id: The integer id of the todo to fail.
        """
        return "Successfully marked todo as failed:\n" + await self._find_and_update(
            todo_id, State.FAILED
        )

    async def no_longer_plan_todo_by_id(self, todo_id: int):
        """Mark a todo as NO_LONGER_PLANNED; raises ValueError if not found.

        Args:
            todo_id: The integer id of the todo to deprioritize.
        """
        return (
            "Successfully marked todo as no longer planned:\n"
            + await self._find_and_update(todo_id, State.NO_LONGER_PLANNED)
        )

    async def make_all_no_longer_planned(self):
        """Mark all NOT_STARTED and IN_PROGRESS todos as NO_LONGER_PLANNED; leaves COMPLETED and FAILED unchanged."""
        affected = 0
        async with self._lock:
            for todo in self._get_all_todos():
                if todo.state in {State.NOT_STARTED, State.IN_PROGRESS}:
                    todo.update_state(State.NO_LONGER_PLANNED)
                    affected += 1
        return f"Marked {affected} todo(s) as no longer planned."

    async def update_todo_by_id(self, todo_id: int, new_state: State):
        """Transition a todo to an arbitrary state; raises ValueError if not found.

        Args:
            todo_id: The integer id of the todo to update.
            new_state: The State to transition the todo to.
        """
        return "Successfully updated todo:\n" + await self._find_and_update(
            todo_id, new_state
        )

    async def pretty_dashboard(self) -> str:
        """Return a human-readable dashboard of active todos, or 'No todos found.'"""
        async with self._lock:
            lines = [
                t.simplified_print()
                for t in self._get_all_todos()
                if t.state != State.NO_LONGER_PLANNED
            ]
        if not lines:
            return "No todos found."
        return "To-Dos\n" + "\n".join(lines)

    @classmethod
    def prompt(cls) -> str:
        """Return the system prompt instructing an LLM how to use this toolset."""
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
        """Return the list of RTFunction nodes for all public tools in this toolset."""
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
