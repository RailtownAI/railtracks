from __future__ import annotations

from .system_one.provider import TypeSafeCompatibleAI


class UpstageAI(TypeSafeCompatibleAI):
    """Upstage's Solar Decide on Upstage's own API (model ``solar-decide``).

    Upstage serves it at ``https://api.upstage.ai/v1/systemone`` in the same format as
    TypeSafe (https://console.upstage.ai/api/systemone). Reads ``UPSTAGE_API_KEY``
    (required); for the Korea region pass ``api_base="https://kr.api.upstage.ai"``.
    A Choice takes at most 26 options: the endpoint scores single-token labels A to Z.
    """

    provider_name = "upstage"
    default_api_base = "https://api.upstage.ai"
    api_key_env = "UPSTAGE_API_KEY"
    requires_api_key = True
    pricing_prefixes = ("upstage",)
    max_choice_labels = 26
