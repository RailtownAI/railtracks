import pytest
from railtracks.llm.models._hyperparameter_support import (
    default_reasoning_effort_for_tools,
    find_mutually_exclusive_conflict,
    is_hyperparameter_supported,
)


class TestManualDenylist:
    """Hyperparameters litellm mis-reports as supported (see litellm#26444) must be
    denied regardless of what litellm.get_supported_openai_params says."""

    @pytest.mark.parametrize(
        "model_name,hyperparameter",
        [
            ("claude-opus-4-7", "temperature"),
            ("claude-opus-4-7-20260519", "temperature"),
            ("anthropic/claude-opus-4-7", "top_p"),
            ("claude-opus-4-8", "temperature"),
            ("claude-opus-4-8", "top_p"),
        ],
    )
    def test_known_bad_combo_denied(self, model_name, hyperparameter):
        assert (
            is_hyperparameter_supported(model_name, "anthropic", hyperparameter)
            is False
        )

    def test_unaffected_anthropic_model_still_allows_temperature(self):
        assert (
            is_hyperparameter_supported("claude-opus-4-1", "anthropic", "temperature")
            is True
        )

    @pytest.mark.parametrize(
        "model_name,hyperparameter",
        [
            ("gemini-2.5-flash", "frequency_penalty"),
            ("gemini-2.5-flash", "presence_penalty"),
            ("vertex_ai/gemini-2.5-pro", "frequency_penalty"),
        ],
    )
    def test_gemini_penalty_hyperparameters_denied(self, model_name, hyperparameter):
        # Gemini's API rejects both penalty hyperparameters with a 400 ("Penalty is not
        # enabled for models/...") despite litellm reporting them as supported.
        assert (
            is_hyperparameter_supported(model_name, "vertex_ai", hyperparameter)
            is False
        )

    def test_gemini_temperature_still_allowed(self):
        assert (
            is_hyperparameter_supported("gemini-2.5-flash", "vertex_ai", "temperature")
            is True
        )


class TestMutualExclusion:
    """Anthropic rejects specifying temperature and top_p together, even though each
    is individually supported (confirmed empirically across every Anthropic model
    tested, not just Opus 4.7/4.8)."""

    def test_temperature_and_top_p_conflict_on_anthropic(self):
        conflict = find_mutually_exclusive_conflict(
            "anthropic", frozenset({"temperature", "top_p"})
        )
        assert conflict == frozenset({"temperature", "top_p"})

    def test_single_hyperparameter_no_conflict(self):
        assert (
            find_mutually_exclusive_conflict("anthropic", frozenset({"temperature"}))
            is None
        )

    def test_no_conflict_on_other_providers(self):
        assert (
            find_mutually_exclusive_conflict(
                "openai", frozenset({"temperature", "top_p"})
            )
            is None
        )


class TestLitellmFallback:
    def test_supported_hyperparameter_reported_true(self):
        # gpt-4o supports temperature per litellm.get_supported_openai_params
        assert is_hyperparameter_supported("gpt-4o", "openai", "temperature") is True

    def test_unsupported_hyperparameter_reported_false(self):
        # gpt-4o is not a reasoning model; verbosity should not be reported supported
        assert is_hyperparameter_supported("gpt-4o", "openai", "verbosity") is False

    def test_litellm_error_fails_open(self, monkeypatch):
        import railtracks.llm.models._hyperparameter_support as hyperparameter_support_module

        def _raise(*args, **kwargs):
            raise RuntimeError("litellm blew up")

        monkeypatch.setattr(
            hyperparameter_support_module.litellm, "get_supported_openai_params", _raise
        )
        assert (
            is_hyperparameter_supported("some-model", "openai", "temperature") is True
        )


class TestDefaultReasoningEffortForTools:
    """#1394: OpenAI reasoning models (gpt-5.4+ family) silently substitute their own
    non-'none' default `reasoning_effort` server-side when the caller omits it, and that
    default conflicts with function tools on `/v1/chat/completions`. Force
    `reasoning_effort='none'` in exactly that situation, and leave every other case alone."""

    @staticmethod
    def _patch_model_info(monkeypatch, **info):
        import railtracks.llm.models._hyperparameter_support as hyperparameter_support_module

        monkeypatch.setattr(
            hyperparameter_support_module.litellm,
            "get_model_info",
            lambda model: info,
        )

    def test_forces_none_when_unset_with_tools_on_reasoning_model(self, monkeypatch):
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=True
        )
        assert (
            default_reasoning_effort_for_tools(
                "openai/gpt-5.6-sol", None, has_tools=True
            )
            == "none"
        )

    def test_explicit_reasoning_effort_not_overridden(self, monkeypatch):
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=True
        )
        assert (
            default_reasoning_effort_for_tools(
                "openai/gpt-5.6-sol", "high", has_tools=True
            )
            == "high"
        )

    def test_no_default_without_tools(self, monkeypatch):
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=True
        )
        assert (
            default_reasoning_effort_for_tools(
                "openai/gpt-5.6-sol", None, has_tools=False
            )
            is None
        )

    def test_non_reasoning_model_untouched(self, monkeypatch):
        # e.g. gpt-4o: no reasoning capability at all, so no implicit-default problem.
        self._patch_model_info(
            monkeypatch, supports_reasoning=None, supports_none_reasoning_effort=None
        )
        assert (
            default_reasoning_effort_for_tools("openai/gpt-4o", None, has_tools=True)
            is None
        )

    def test_reasoning_model_without_none_support_untouched(self, monkeypatch):
        # A reasoning model whose accepted efforts don't include "none" (e.g. only
        # medium/high/xhigh) -- forcing "none" would just trade one 400 for another.
        self._patch_model_info(
            monkeypatch, supports_reasoning=True, supports_none_reasoning_effort=False
        )
        assert (
            default_reasoning_effort_for_tools(
                "openai/gpt-5.5-pro", None, has_tools=True
            )
            is None
        )

    def test_litellm_error_fails_open(self, monkeypatch):
        import railtracks.llm.models._hyperparameter_support as hyperparameter_support_module

        def _raise(*args, **kwargs):
            raise Exception("This model isn't mapped yet.")

        monkeypatch.setattr(
            hyperparameter_support_module.litellm, "get_model_info", _raise
        )
        assert (
            default_reasoning_effort_for_tools(
                "openai/some-unknown-model", None, has_tools=True
            )
            is None
        )
