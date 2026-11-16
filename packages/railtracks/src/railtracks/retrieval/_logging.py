"""Loggers for the retrieval subsystem.

Plain ``logging`` loggers under the ``RT`` logger: records reach railtracks' console
and file handlers without needing a run context, since ingestion often runs outside a
Flow. They are named by component so the console's short label tells them apart.
"""

import logging
from enum import Enum


class RetrievalComponent(str, Enum):
    """The retrieval components that log, each with its own logger."""

    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    LOADER = "loader"
    RUNTIME = "runtime"
    STORE = "store"


def get_logger(component: RetrievalComponent) -> logging.Logger:
    """The logger for one retrieval component.

    Args:
        component: The component to log for, such as ``RetrievalComponent.STORE``.

    Returns:
        The ``RT.retrieval.<component>`` logger.
    """
    return logging.getLogger(f"RT.retrieval.{component.value}")
