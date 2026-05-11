"""Retry strategies for LLM API calls.

Pass a ``RetryApproach`` subclass as ``retry_approach`` when constructing any
provider LLM (e.g. ``AnthropicLLM``, ``OpenAILLM``) to automatically retry on
transient errors such as rate-limit and timeout responses.  Raises
``RetryError`` (preserving every attempt's exception) once all tries are
exhausted.
"""

from .base import RetryApproach
from .exponential import ExponentialRetry
from .fixed import FixedRetry
from .linear import LinearRetry

__all__ = [
    "ExponentialRetry",
    "FixedRetry",
    "RetryApproach",
    "LinearRetry",
]
