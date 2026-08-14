"""Tests for the 1.5.0 pending-change notices.

Every notice has two halves, and both are tested:

1. The deprecated spelling emits a ``FutureWarning``.
2. The forward spelling is **silent** — otherwise the notice sends users to something
   that warns just as loudly, and a clean run is impossible.

The silent half catches the real mistakes. A notice sited on an internal code path fires
during ``import railtracks`` or on every node build, which makes it both useless and
unsuppressable.

TODO: Delete this file with the notices in 1.5.0.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings

import pytest

import railtracks as rt
from railtracks.utils.deprecation import NEXT_VERSION, UPGRADE_GUIDE, warn_pending_change

RELOCATED_GUARDS = [
    "BlockTextInputGuard",
    "InputLengthGuard",
    "PIIRedactInputGuard",
    "BlockTextOutputGuard",
    "OutputLengthGuard",
    "PIIRedactOutputGuard",
]

PII_CONFIG = ["PIICustomPattern", "PIIEntity", "PIIRedactConfig"]

RELOCATED = RELOCATED_GUARDS + PII_CONFIG

# removed in 1.5.0, still reachable from `rt.guardrails` with a notice
REMOVED_GUARDRAIL_NAMES = ["Guard", "Guardrail", "BaseGuardrail", "BaseLLMGuardrail"]

# unchanged in 1.5.0 — these must never warn, or users will over-migrate
SURVIVING_GUARDRAIL_NAMES = [
    "InputGuard",
    "OutputGuard",
    "GuardrailAction",
    "GuardrailDecision",
    "GuardrailTrace",
    "GuardrailBlockedError",
    "LLMGuardrailEvent",
    "LLMGuardrailPhase",
]

# providers constructible without network access or an optional extra
OFFLINE_PROVIDERS = [
    ("OpenAILLM", "gpt-4o"),
    ("GeminiLLM", "gemini-2.5-flash"),
    ("CohereLLM", "command-r"),
    ("AzureAILLM", "azure/deployment"),
]


def assert_silent(fn):
    """Run `fn`, failing if it emits any pending-change notice."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        return fn()


# ---------------------------------------------------------------------------------------
# the helper
# ---------------------------------------------------------------------------------------


def test_message_names_version_and_guide():
    with pytest.warns(FutureWarning) as record:
        warn_pending_change("thing", change="moves", instead="other.thing")

    message = str(record[0].message)
    assert f"thing moves in railtracks {NEXT_VERSION}." in message
    assert "Use other.thing instead." in message
    assert UPGRADE_GUIDE in message


def test_no_replacement_is_invented_when_none_exists():
    with pytest.warns(FutureWarning) as record:
        warn_pending_change("thing", change="is removed")

    assert "Use " not in str(record[0].message)


def test_category_is_future_warning():
    """DeprecationWarning is hidden by default outside __main__, so it must not be used."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_pending_change("thing")

    assert [w.category for w in caught] == [FutureWarning]


# ---------------------------------------------------------------------------------------
# notices must never fire on an internal path
# ---------------------------------------------------------------------------------------


def test_importing_railtracks_is_silent():
    """`import railtracks` in a fresh interpreter must emit no notice.

    Run as a subprocess so this is a true first import, unaffected by test-session state,
    with -W error::FutureWarning so any stray notice exits non-zero.
    """
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", "import railtracks"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"`import railtracks` emitted a pending-change notice:\n{result.stderr}"
    )


def test_building_a_normal_agent_is_silent():
    assert_silent(lambda: rt.agent_node(name="quiet", llm=rt.llm.OpenAILLM("gpt-4o")))


def test_core_entry_points_are_silent():
    assert_silent(lambda: (rt.call, rt.Flow, rt.function_node, rt.Session, rt.broadcast))


# ---------------------------------------------------------------------------------------
# agent_node(llm=...)
# ---------------------------------------------------------------------------------------





def test_agent_node_with_llm_is_silent():
    assert_silent(lambda: rt.agent_node(name="with-llm", llm=rt.llm.OpenAILLM("gpt-4o")))


# ---------------------------------------------------------------------------------------
# guardrails.llm.* -> prebuilt.guardrails.*
# ---------------------------------------------------------------------------------------



@pytest.mark.parametrize("name", RELOCATED)
def test_prebuilt_guardrails_forward_path_is_silent(name):
    assert_silent(lambda: getattr(rt.prebuilt.guardrails, name))


def test_removed_names_are_not_advertised_but_stay_discoverable():
    """Out of __all__ so pdoc does not try to resolve them; in __dir__ so completion works."""
    for name in REMOVED_GUARDRAIL_NAMES:
        assert name not in rt.guardrails.__all__
        assert name in dir(rt.guardrails)






def test_rt_interactive_warns():
    with pytest.warns(FutureWarning, match="rt.interactive is removed"):
        rt.interactive


def test_rt_interactive_warns_on_every_access():
    """Must not be cached into globals(), or the notice fires only once per process."""
    for _ in range(2):
        with pytest.warns(FutureWarning, match="rt.interactive is removed"):
            rt.interactive


def test_local_chat_warns():
    module = importlib.import_module("railtracks.interaction")

    with pytest.warns(FutureWarning, match="local_chat is removed"):
        module.local_chat


# ---------------------------------------------------------------------------------------
# decisions that were deliberately rejected — these must stay silent
# ---------------------------------------------------------------------------------------





def test_broadcast_callback_is_silent():
    """No notice: `broadcast_callback` keeps its signature *and* its meaning in 1.5.0.
    Only the internal message class is renamed. See design-docs/warnings §3.6."""
    assert_silent(lambda: rt.ExecutorConfig(broadcast_callback=lambda item: None))


def test_node_subclassing_is_silent():
    """Notice skipped by decision. See design-docs/warnings §3.5."""
    from railtracks.nodes.nodes import Node

    def define_subclass():
        class MyNode(Node):
            def details(self):
                return {}

            async def invoke(self):
                return None

            @classmethod
            def name(cls):
                return "MyNode"

            @classmethod
            def type(cls):
                return "Other"

        return MyNode

    assert_silent(define_subclass)