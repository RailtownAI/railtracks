from __future__ import annotations

import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass
class Stamp:
    """
    A simple dataclass that represents a stamp in time for the system.

    Shared actions should have identical stamps, but they do not need to have identical time fields.
    """

    time: float
    step: int
    identifier: str

    def __lt__(self, other):
        # ordering by time is always the fallback
        if self.step == other.step:
            return self.time < other.time
        return self.step < other.step

    def __hash__(self):
        return hash((self.time, self.step, self.identifier))


class StampManager:
    """
    A simple manager object that can be used to coordinate the creation of a stamps during the runtime of a system.
    """

    def __init__(self):
        """Creates a new instance of a `StampManager` object. It defaults the current step to 0."""
        self._step = 0
        self._stamp_lock = self._create_lock()
        self._step_logs: Dict[int, List[str]] = {self._step: []}
        self._stamps = []

    def create_stamp(self, message: str) -> Stamp:
        """
        Creates a new stamp with the given message.

        Args:
            message (str): The message you would like the returned stamp to contain

        Returns:
            Stamp: The newly created stamp with the next step value, your provided message and a timestamp determined
             at creation.
        """
        with self._stamp_lock:
            if self._step not in self._step_logs:
                self._step_logs[self._step] = []
            st = Stamp(time.time(), self._step, message)
            self._step_logs[self._step].append(message)
            self._step += 1
            self._stamps.append(st)

            return st

    def stamp_creator(self) -> Callable[[str], Stamp]:
        """
        Creates a method that can be used to create new stamps with shared step values.

        This method guarantees the following properties:

        - The stamp created by calling the method will have the timestamp of when the method was called.
        - You can have different messages for each stamp created by the method.
        - All stamps created by the method will share step values

        Returns:
            (str) -> Stamp: A method that can be used to create new stamps with shared step values.
        """
        with self._stamp_lock:
            if self._step not in self._step_logs:
                self._step_logs[self._step] = []

            stepped_value = self._step  # python integers are immutable!
            self._step += 1

        def new_stamp(message: str):
            with self._stamp_lock:
                self._step_logs[stepped_value].append(message)
                st = Stamp(time.time(), stepped_value, message)
                self._stamps.append(st)
                return st

        return new_stamp

    @classmethod
    def _create_lock(cls):
        """
        Creates a new lock object
        """
        return threading.Lock()

    @property
    def step_logs(self):
        """Returns a copy of a dictionary containing a list of identifiers for each step that exist in the system."""
        return deepcopy(self._step_logs)

    @property
    def all_stamps(self):
        """Returns a list of the all the stamps that have been created in the system."""
        return deepcopy(sorted(self._stamps))

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != "_stamp_lock"}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._stamp_lock = self._create_lock()
