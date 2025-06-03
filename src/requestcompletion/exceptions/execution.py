from . import RCError

from ..state.request import RequestTemplate
from ..info import ExecutionInfo


class ExecutionError(RCError):
    """A general exception thrown when an error occurs during the execution of the graph."""

    # note we are allowing any exception to be passed, it need not be an exception from RC.
    def __init__(
        self,
        failed_request: RequestTemplate,
        execution_info: ExecutionInfo,
        final_exception: Exception,
    ):
        """
        Creates a new instance of an ExecutionError

        Args:
            failed_request: The request that failed during the execution that triggered this exception
            final_exception: The last exception that was thrown during the execution (this is likely the one that cause the execution exception)
        """
        self.failed_request = failed_request
        self.execution_info = execution_info
        self.final_exception = final_exception
        super().__init__(
            f"The final nodes exception was {final_exception}, in the failed request {failed_request}."
            f"A complete history of errors seen is seen here: \n {self.exception_history}"
        )

    @property
    def exception_history(self):
        return self.execution_info.exception_history


class GlobalTimeOutError(RCError):
    """A general exception to be thrown when a global timeout has been exceeded during execution."""

    def __init__(self, timeout: float):
        super().__init__(f"Execution timed out after {timeout} seconds")
