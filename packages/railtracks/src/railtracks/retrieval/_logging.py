"""Loggers for the retrieval subsystem.

Plain ``logging`` loggers under the ``RT`` logger: records reach railtracks' console
and file handlers without needing a run context, since ingestion often runs outside a
Flow. They are named by component so the console's short label tells them apart.
"""

import logging


def get_logger(component: str) -> logging.Logger:
    """The logger for one retrieval component.

    Args:
        component: The component's name, such as ``"embedding"`` or ``"store"``.

    Returns:
        The ``RT.retrieval.<component>`` logger.
    """
    return logging.getLogger(f"RT.retrieval.{component}")
