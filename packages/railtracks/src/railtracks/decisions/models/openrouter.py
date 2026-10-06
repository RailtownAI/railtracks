from __future__ import annotations

from .system_one.provider import TypeSafeCompatibleAI


class OpenRouterAI(TypeSafeCompatibleAI):
    """System One models through OpenRouter's ``/api/v1/systemone`` mirror.

    Model ids carry the vendor, e.g. ``typesafe/jev-1.13``. Reads ``OPENROUTER_API_KEY``
    (required). OpenRouter reports the billed ``usage.cost`` and the serving
    ``provider``, which the response uses over the catalog price and this host's name.
    """

    provider_name = "openrouter"
    default_api_base = "https://openrouter.ai/api"
    api_key_env = "OPENROUTER_API_KEY"
    requires_api_key = True
    pricing_prefixes = ("openrouter",)
