from __future__ import annotations

from .system_one.provider import TypeSafeCompatibleAI


class LayaAI(TypeSafeCompatibleAI):
    """A self-hosted Laya server (``laya-serve``), e.g. the ``english`` checkpoint.

    There is no public endpoint: pass ``api_base=`` or set ``LAYA_API_BASE``.
    ``LAYA_API_KEY`` is optional, matching the server's own optional bearer auth.
    Limits: https://github.com/NandhaKishorM/laya/blob/main/docs/http-api.md.
    """

    provider_name = "laya"
    api_base_env = "LAYA_API_BASE"
    api_key_env = "LAYA_API_KEY"
    pricing_prefixes = ("laya",)
    max_choice_labels = 100
    max_questions = 64
    max_state_chars = 50_000
