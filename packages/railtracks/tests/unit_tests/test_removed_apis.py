"""The legacy human-in-the-loop package and local chat UI were removed in #1830."""

import importlib

import pytest


@pytest.mark.parametrize(
    ("module_name", "name"),
    [
        ("railtracks", "interactive"),
        ("railtracks.interaction", "local_chat"),
        ("railtracks.exceptions", "VisualExtraRequiredError"),
    ],
)
def test_removed_names_raise_attribute_error(module_name, name):
    module = importlib.import_module(module_name)

    with pytest.raises(AttributeError):
        getattr(module, name)
    assert name not in dir(module)


def test_human_in_the_loop_package_is_removed():
    with pytest.raises(ImportError):
        from railtracks.human_in_the_loop import HIL, ChatUI, HILMessage  # noqa: F401


def test_interactive_module_is_removed():
    with pytest.raises(ImportError):
        from railtracks.interaction.interactive import local_chat  # noqa: F401
