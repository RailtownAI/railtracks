import inspect
from typing import TypeVar, Generic, Callable

from ..nodes import Node
from ..run.info import ExecutionInfo
from ..run.state.request import RequestTemplate

####################################################################################################
# Node Exceptions
# I have chosen to have explicit exception subtypes instead of passing in those details as arguments to single base case
#  This was a design choice that could be challenged. I have no major issues either way.
####################################################################################################


_TOutput = TypeVar("_TOutput")


class MalformedFunctionException(Exception):
    """
    A special exception type that is thrown when a one of the update function or post node function in RC have
     malformed types

    This exception should be human-readable because it will be surfaced to the user.
    """

    # TODO point this exception stack trace to the bad function and not the internals.

    def __init__(self, bad_function: Callable, message: str):
        """
        Creates a new instance of a MalformedTypeException

        Args:
            bad_function (Callable): The function that lead to the error
            message (str): The descriptive message about the specific issue that occurred
        """
        super().__init__(message)
        self.bad_function = bad_function

    def __str__(self):
        return f"MalformedTypeException: {super().__str__()}\n{self.collect_function_info()}"

    def collect_function_info(self):
        """
        Converts the provided function into
        """
        name = self.bad_function.__name__
        try:
            source_code = inspect.getsource(self.bad_function)
        except OSError:
            source_code = "Unknown"
        try:
            line_number = inspect.getsourcelines(self.bad_function)[1]
        except OSError:
            line_number = "Unknown"

        source_file = inspect.getsourcefile(self.bad_function)
        if source_file is None:
            source_file = "Unknown"

        return f"({name} in {source_file} at line {line_number})\n{source_code}"
