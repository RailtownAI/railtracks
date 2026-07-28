import pytest
from railtracks.llm.models._param_support import (
    find_mutually_exclusive_conflict,
    is_param_supported,
)


class TestManualDenylist:
    """Params litellm mis-reports as supported (see litellm#26444) must be denied
    regardless of what litellm.get_supported_openai_params says."""

    @pytest.mark.parametrize(
        "model_name,param",
        [
            ("claude-opus-4-7", "temperature"),
            ("claude-opus-4-7-20260519", "temperature"),
            ("anthropic/claude-opus-4-7", "top_p"),
            ("claude-opus-4-8", "temperature"),
            ("claude-opus-4-8", "top_p"),
        ],
    )
    def test_known_bad_combo_denied(self, model_name, param):
        assert is_param_supported(model_name, "anthropic", param) is False

    def test_unaffected_anthropic_model_still_allows_temperature(self):
        assert is_param_supported("claude-opus-4-1", "anthropic", "temperature") is True

    @pytest.mark.parametrize(
        "model_name,param",
        [
            ("gemini-2.5-flash", "frequency_penalty"),
            ("gemini-2.5-flash", "presence_penalty"),
            ("vertex_ai/gemini-2.5-pro", "frequency_penalty"),
        ],
    )
    def test_gemini_penalty_params_denied(self, model_name, param):
        # Gemini's API rejects both penalty params with a 400 ("Penalty is not
        # enabled for models/...") despite litellm reporting them as supported.
        assert is_param_supported(model_name, "vertex_ai", param) is False

    def test_gemini_temperature_still_allowed(self):
        assert (
            is_param_supported("gemini-2.5-flash", "vertex_ai", "temperature") is True
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

    def test_single_param_no_conflict(self):
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
    def test_supported_param_reported_true(self):
        # gpt-4o supports temperature per litellm.get_supported_openai_params
        assert is_param_supported("gpt-4o", "openai", "temperature") is True

    def test_unsupported_param_reported_false(self):
        # gpt-4o is not a reasoning model; verbosity should not be reported supported
        assert is_param_supported("gpt-4o", "openai", "verbosity") is False

    def test_litellm_error_fails_open(self, monkeypatch):
        import railtracks.llm.models._param_support as param_support_module

        def _raise(*args, **kwargs):
            raise RuntimeError("litellm blew up")

        monkeypatch.setattr(
            param_support_module.litellm, "get_supported_openai_params", _raise
        )
        assert is_param_supported("some-model", "openai", "temperature") is True
