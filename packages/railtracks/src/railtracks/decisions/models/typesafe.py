from __future__ import annotations

from .system_one.provider import SystemOneProvider


class TypeSafeAI(SystemOneProvider):
    """TypeSafe's hosted System One models, e.g. ``jev-latest``.

    Reads ``TYPESAFE_API_KEY`` (required) and, optionally, ``TYPESAFE_API_BASE``.
    Wire format: https://docs.typesafe.ai/api.
    """

    provider_name = "typesafe"
    default_api_base = "https://api.typesafe.ai"
    api_base_env = "TYPESAFE_API_BASE"
    api_key_env = "TYPESAFE_API_KEY"
    requires_api_key = True
    pricing_prefixes = ("typesafe",)
