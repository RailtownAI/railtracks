from __future__ import annotations

from collections import defaultdict
import railtracks as rt
from typing import Callable

from pydantic import BaseModel, Field
from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.utils.logging.create import get_rt_logger

from ._base import ToolSet

from ...context.central import get_parent_id

from enum import Enum

logger = get_rt_logger(__name__)

class State(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ToDo(BaseModel):
    short_description: str = Field(description="...")
    description: str = Field(description="...")
    state: State = Field(description="...", default=State.NOT_STARTED)

    # TODO: add validation here.

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
    def __init__(self, add_callback: Callable[[str, str, State], None] | None = None):
        self.todos: dict[str, list[ToDo]] = defaultdict(list)
        self.misc_todos: list[ToDo] = []

        if add_callback is None:
            def default_add_callback(short_description: str, description: str, state: State):
                # default is to do nothing.
                pass
            add_callback = default_add_callback

        self.add_callback = add_callback

    def add(self, short_description: str, description: str, state: State = State.NOT_STARTED):
        """Add a new todo scoped to the current node context.

        Args:
            short_description: Brief, unique label for the todo (used as its identifier in listings).
            description: Full details of what needs to be done.
            state: Initial state of the todo. Defaults to NOT_STARTED.

        Raises:
            ValueError: If a todo with the same short_description or description already exists.
        """
        parent_id = get_parent_id()
        try:
            self.add_callback(short_description, description, state)
        except Exception as e:
            logger.error(f"Error in callback for todo: {e}")

        to_do = ToDo(short_description=short_description, description=description, state=state)
        validity_check = self.check_if_valid(self.get_all_todos(), to_do)
        if validity_check is not None:
            raise ValueError(validity_check)

        if parent_id is None:
            self.misc_todos.append(to_do)
        else:
            self.todos[parent_id].append(to_do)

    @classmethod
    def check_if_valid(_cls, todos: list[ToDo], todo_to_add: ToDo) -> str | None:
        if todo_to_add.short_description in [todo.short_description for todo in todos]:
            return f"Todo with short description '{todo_to_add.short_description}' already exists. Please provide a unique short description."
        
        if todo_to_add.description in [todo.description for todo in todos]:
            return f"Todo with description '{todo_to_add.description}' already exists. Please provide a unique description."
        
        if todo_to_add.identifier in [todo.identifier for todo in todos]:
            raise ValueError(f"Todo with identifier '{todo_to_add.identifier}' already exists. Please provide a unique identifier.")
        
        return None

    def get_all_todos(self) -> list[ToDo]:
        """Return all todos for the current node context.

        Returns:
            List of ToDo objects scoped to the current node, or misc todos if called outside a node.
        """
        parent_id = get_parent_id()
        if parent_id is None:
            return self.misc_todos  
        
        return self.todos[parent_id]
    
    def get_completed_todos(self) -> list[str]:
        """Return formatted strings for all completed todos in the current context.

        Returns:
            List of complete_print() strings for todos in COMPLETED state.
        """
        return [todo.complete_print() for todo in self.get_all_todos() if todo.state == State.COMPLETED]

    def get_not_started_todos(self) -> list[str]:
        """Return formatted strings for todos that have not been started in the current context.

        Returns:
            List of complete_print() strings for todos in NOT_STARTED state.
        """
        return [todo.complete_print() for todo in self.get_all_todos() if todo.state == State.NOT_STARTED]

    def get_incomplete_todos(self) -> list[str]:
        """Return formatted strings for all unfinished todos (not started or in progress).

        Returns:
            List of complete_print() strings for todos in NOT_STARTED or IN_PROGRESS state.
        """
        return [todo.complete_print() for todo in self.get_all_todos() if todo.state == State.NOT_STARTED or todo.state == State.IN_PROGRESS]

    def complete_todo_by_id(self, todo_id: int):
        """Mark a todo as COMPLETED.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in the current context.
        """
        for todo in self.get_all_todos():
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
            ValueError: If no todo with the given id exists in the current context.
        """
        for todo in self.get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(State.IN_PROGRESS)
                return "Successfully started todo:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def update_todo_by_id(self, todo_id: int, new_state: State):
        """Update a todo to an arbitrary state.

        Args:
            todo_id: The integer identifier of the todo (from ToDo.identifier).
            new_state: The target State to transition the todo to.

        Returns:
            Confirmation string with the updated todo details.

        Raises:
            ValueError: If no todo with the given id exists in the current context.
        """
        for todo in self.get_all_todos():
            if todo.identifier == todo_id:
                todo.update_state(new_state)
                return "Successfully updated todo:\n" + todo.complete_print()
        raise ValueError(f"Todo with identifier '{todo_id}' not found.")

    def pretty_dashboard(self) -> str:
        """Return a human-readable summary of all todos in the current context.

        Returns:
            Formatted string listing each todo's state and short description, or a
            'No todos found.' message if none exist.
        """
        todos = self.get_all_todos()
        if not todos:
            return "No todos found."

        dashboard_str = "To-Dos\n"
        for todo in todos:
            dashboard_str += todo.simplified_print() + "\n"
        
        return dashboard_str.strip()

    @classmethod
    def prompt(cls) -> str:
        return (
            "Use the todo tools to track tasks throughout your work. "
            "Before starting, call add() for each task you plan to complete. "
            "Call start_todo_by_id() when you begin a task and complete_todo_by_id() when it is done. "
            "Use pretty_dashboard() to review current progress. "
            "Each todo must have a unique short_description and description. "
            "Retrieve todo identifiers from get_all_todos() before calling any id-based methods."
        )
    
    
    def tool_set(self) -> list[RTFunction]:
        
        functions = [
            self.add,
            self.complete_todo_by_id,
            self.start_todo_by_id,
            self.update_todo_by_id,
            self.get_all_todos,
            self.get_completed_todos,
            self.get_not_started_todos,
            self.get_incomplete_todos,
        ]

        return [rt.function_node(func) for func in functions]



