from __future__ import annotations


from pydantic import BaseModel, Field

from .utils.logging.config import allowable_log_levels


# There may be moments when you are confused what should be in this config object vs. what should
class ExecutorConfig(BaseModel):
    """
    A class that contains configuration details of the executor that will be used to execute the graph.

    This class is designed to have a majority of default values that are allowed to be overridden by the user as needed.
    """

    timeout: float = Field(
        default=25,
        description="The maximum number of time in seconds you would like to wait for a response.",
    )

    force_close_streams: bool = Field(
        default=True,
        description="If true the executor will force close any open streams when it finishes execution.",
    )
    end_on_error: bool = Field(
        default=False,
        description="If true the executor will stop execution when an error is encountered.",
    )
    # Make sure that this default is in line with allowable_log_levels
    logging_setting: allowable_log_levels = Field(
        default="VERBOSE",
        description="The setting for the level of logging you would like to have.",
    )
    # logging_file: str | None = Field(
    #     default=None,
    #     description="If you would like to save the logs to a file, provide the file path here. Otherwise it will use the command line",
    # )
    # file_logging_config: dict | None = Field(
    #     default=None,
    #     description="If you would like to specify the file logging config, provide the configuration here.",
    # )
    # file_logging_level: Optional[logging.DEBUG | logging.INFO | logging.WARNING | logging.ERROR | logging.CRITICAL] = Field(
    #     default=None,
    #     description="If you would like to specify the file logging level, provide the level here.",
    # )
