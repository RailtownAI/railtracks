from __future__ import annotations

from ..model import DecisionModel


class TypeSafeAI(DecisionModel):
    """TypeSafe's hosted System One models, e.g. ``jev-latest``.

    Calls ``litellm.adecisions`` with ``typesafe/<model_name>``. litellm reads
    ``TYPESAFE_API_KEY`` (required) and, optionally, ``TYPESAFE_API_BASE``. Text and
    JSON input only. API: https://docs.typesafe.ai/api.
    """

    provider_prefix = "typesafe"
    provider_name = "typesafe"
