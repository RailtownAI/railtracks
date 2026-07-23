"""
Tests for railtracks.llm.models._param_support (issue #1276).

Mirrors src/railtracks/llm/models/_param_support.py — this module does not exist
yet, so these tests are expected to fail (ModuleNotFoundError) until it's added.
"""

import pytest
from railtracks.llm.models._param_support import is_param_supported


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
