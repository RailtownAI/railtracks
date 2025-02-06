from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutorConfig(BaseModel):
    """
    A class that contains configuration details of the executor that will be used to execute the graph.

    This class is designed to have a majority of default values that are allowed to be overridden by the user as needed.
    """

    global_num_retries: int = Field(
        default=6,
        description="The maximum number of retries before the executor will throw an exception and exit early.",
    )
    retry_upstream_request_on_failure: bool = Field(
        default=True,
        description="If true the framework will use the scorched earth method to handle errors. Otherwise it will halt the execution when an error is thrown without a completion protocol",
    )
    timeout: float = Field(
        default=25,
        description="The maximum number of time in seconds you would like to wait for a response.",
    )
    force_close_streams: bool = Field(
        default=True,
        description="If true the executor will force close any open streams when it finishes execution.",
    )
    workers: int = Field(
        default=150,
        description="The number of threads that will be used to execute the graph.",
    )
    DEBUG: bool = Field(
        default=False, description="If true the executor will run in debug mode"
    )
