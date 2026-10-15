from __future__ import annotations

from ..model import DecisionModel


class OpenRouterAI(DecisionModel):
    """System One models through OpenRouter's decisions endpoint.

    Model ids carry the vendor, e.g. ``typesafe/jev-1.13``; calls
    ``litellm.adecisions`` with ``openrouter/<model_name>``. litellm reads
    ``OPENROUTER_API_KEY`` (required) and, optionally, ``OPENROUTER_API_BASE``. Text and
    JSON input only.
    """

    provider_prefix = "openrouter"
    provider_name = "openrouter"
