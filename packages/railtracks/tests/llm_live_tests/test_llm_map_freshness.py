"""Fails when a model in ``llm_map`` is gone or close to deprecation.

OpenAI, Anthropic and Gemini models are checked against litellm's model catalog
(``litellm.model_cost``, fetched at import). Hugging Face models are checked against the
Hugging Face router's live model list, since litellm does not catalog them.
"""

from datetime import date, timedelta

import httpx
import litellm
import pytest

from .llm_map import llm_map

DEPRECATION_WARNING_WINDOW = timedelta(days=60)
HF_ROUTER_MODELS_URL = "https://router.huggingface.co/v1/models"

CATALOG_PROVIDERS = {k: v for k, v in llm_map.items() if k != "huggingface"}


def _catalog_entry(model_name: str) -> dict | None:
    """Look the model up as ``provider/name``, then as the bare ``name``."""
    _, _, bare_name = model_name.partition("/")
    return litellm.model_cost.get(model_name) or litellm.model_cost.get(bare_name)


@pytest.mark.parametrize(
    "llm", CATALOG_PROVIDERS.values(), ids=CATALOG_PROVIDERS.keys()
)
def test_model_is_in_the_catalog_and_not_deprecating(llm):
    model_name = llm.model_name()
    entry = _catalog_entry(model_name)
    assert entry is not None, (
        f"{model_name} is not in litellm's model catalog; update llm_map.py"
    )

    deprecation_date = entry.get("deprecation_date")
    if deprecation_date is None:
        return
    cutoff = date.today() + DEPRECATION_WARNING_WINDOW
    assert date.fromisoformat(deprecation_date) > cutoff, (
        f"{model_name} is deprecated on {deprecation_date}; update llm_map.py"
    )


def test_huggingface_model_is_served_by_its_provider():
    route = llm_map["huggingface"].model_name().removeprefix("huggingface/")
    provider, _, model_id = route.partition("/")
    response = httpx.get(HF_ROUTER_MODELS_URL, timeout=30)
    response.raise_for_status()

    served_by = {
        m["id"]: {p["provider"] for p in m.get("providers", [])}
        for m in response.json()["data"]
    }
    assert provider in served_by.get(model_id, set()), (
        f"{model_id} is no longer served by {provider} on Hugging Face; update llm_map.py"
    )
