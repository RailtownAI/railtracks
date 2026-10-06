from __future__ import annotations

from typing import Literal

import httpx

from railtracks.llm.retries import RetryApproach

from .laya import LayaAI
from .typesafe_compatible.provider import SYSTEM_ONE_PATH, TypeSafeCompatibleAI

Upstream = Literal["typesafe", "laya", "bespoke"]
_UPSTREAMS: tuple[Upstream, ...] = ("typesafe", "laya", "bespoke")


class LiteLLMProxyAI(TypeSafeCompatibleAI):
    """System One models through a LiteLLM proxy's native pass-through routes.

    Sends to ``{api_base}/{upstream}/v1/systemone`` with a LiteLLM virtual key; the
    proxy adds the upstream's own key and tracks spend. Reads ``LITELLM_PROXY_API_BASE``
    (required) and ``LITELLM_PROXY_API_KEY``, the names LiteLLM's own ``litellm_proxy``
    provider uses. Routes: https://docs.litellm.ai/docs/auto_router/decision_classifiers
    (``/laya`` and ``/bespoke`` need a proxy with LiteLLM PR #43626).
    """

    api_base_env = "LITELLM_PROXY_API_BASE"
    api_key_env = "LITELLM_PROXY_API_KEY"

    def __init__(
        self,
        model_name: str,
        *,
        upstream: Upstream,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        """Create a client for one upstream behind the proxy.

        Args:
            model_name: The upstream's model name, e.g. ``"jev-latest"`` or
                ``"english"``; the virtual key needs access to ``{upstream}/{model}``.
            upstream: Which pass-through route to use: ``"typesafe"``, ``"laya"`` or
                ``"bespoke"``.
            api_key: The LiteLLM virtual key. Defaults to ``LITELLM_PROXY_API_KEY``.
            api_base: The proxy's base URL. Defaults to ``LITELLM_PROXY_API_BASE``.
            timeout: Seconds to wait for each HTTP request.
            http_client: An ``httpx.AsyncClient`` to send requests through.
            retry_approach: Retry strategy for transient failures; None makes one
                attempt.

        Raises:
            ValueError: If ``upstream`` is not one of the proxy's decision routes.
        """
        if upstream not in _UPSTREAMS:
            raise ValueError(
                f"upstream must be one of {list(_UPSTREAMS)}, got {upstream!r}"
            )
        super().__init__(
            model_name,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            http_client=http_client,
            retry_approach=retry_approach,
        )
        self.upstream = upstream
        self.provider_name = upstream
        self.path = f"/{upstream}{SYSTEM_ONE_PATH}"
        self.pricing_prefixes = (upstream,)
        if upstream == "laya":
            # the proxy forwards as is, so Laya's own limits still apply
            self.max_choice_labels = LayaAI.max_choice_labels
            self.max_questions = LayaAI.max_questions
            self.max_state_chars = LayaAI.max_state_chars

    def _key_notes(self) -> list[str]:
        return [
            *super()._key_notes(),
            f"The virtual key needs access to the model {self.upstream}/{self.model_name}.",
        ]
