from railtracks.llm import Message, MessageHistory, SystemMessage, UserMessage
from railtracks.llm.message import Role
from railtracks.llm.prompt_injection_utils import (
    ValueDict,
    escape_braces,
    fill_template,
)
from railtracks.utils import prompt_injection


class _Holder:
    def __init__(self):
        self.attr = "attribute-value"


# ================= START fill_template tests ============

def test_fill_template_uses_values():
    assert fill_template("Hello, {name}", {"name": "Test"}) == "Hello, Test"

def test_fill_template_missing_key_returns_placeholder():
    assert fill_template("Hello, {name}", {}) == "Hello, {name}"

def test_fill_template_numeric_key():
    assert fill_template("{1}", {"1": "one"}) == "one"

def test_fill_template_doubled_braces_become_single():
    assert fill_template("{{name}}", {"name": "Test"}) == "{name}"

# ---- placeholders that are left exactly as written ----

def test_fill_template_leaves_attribute_access():
    values = {"holder": _Holder()}
    assert fill_template("{holder.attr}", values) == "{holder.attr}"

def test_fill_template_leaves_chained_attribute_access():
    """A chain is left as written too, not resolved one step at a time."""
    template = "{holder.attr.title}"
    assert fill_template(template, {"holder": _Holder()}) == template

def test_fill_template_leaves_item_access():
    values = {"mapping": {"key": "item-value"}}
    assert fill_template("{mapping[key]}", values) == "{mapping[key]}"

def test_fill_template_leaves_conversion():
    assert fill_template("{name!r}", {"name": "Test"}) == "{name!r}"

def test_fill_template_leaves_format_spec():
    assert fill_template("{name:>20}", {"name": "Test"}) == "{name:>20}"

def test_fill_template_leaves_auto_numbered_placeholder():
    """`{}` has no key to look up. `{0}` is a bare key and is filled like any other."""
    assert fill_template("{}", {"0": "zero"}) == "{}"
    assert fill_template("{0}", {"0": "zero"}) == "zero"

# ---- inputs that must not raise ----

def test_fill_template_unbalanced_brace_returns_template():
    assert fill_template("unbalanced { brace", {}) == "unbalanced { brace"

def test_fill_template_dotted_field_with_no_matching_key():
    """`{a.b}` where `a` is absent must not raise."""
    assert fill_template("look at {config.json} please", {}) == "look at {config.json} please"

def test_fill_template_leaves_untemplated_text_alone():
    for text in ['json {"a": 1}', "css body { color: red }", "handlebars {{x}} here"]:
        assert fill_template(escape_braces(text), {}) == text

# ================ END fill_template tests ===============


# ================= START escape_braces tests ============

def test_escape_braces_doubles_braces():
    assert escape_braces("{a} {b}") == "{{a}} {{b}}"

def test_escape_braces_round_trips_through_fill_template():
    values = {"value": "filled", "holder": _Holder()}
    for text in [
        "Echo {value}",
        "Echo {holder.attr} and {mapping[key]}",
        "unbalanced { and {a.b}",
        'json {"k": {"n": 1}}',
        "already {{doubled}}",
    ]:
        assert fill_template(escape_braces(text), values) == text

def test_escape_braces_protects_only_the_escaped_fragment():
    """A developer template still injects while an escaped fragment does not."""
    values = {"time": "12:00", "value": "filled"}
    template = "Time is {time}:\n" + escape_braces("Echo {value}")
    assert fill_template(template, values) == "Time is 12:00:\nEcho {value}"

# ================ END escape_braces tests ===============


# ================= START ValueDict tests ====================

def test_valuedict_returns_value_if_exists():
    d = prompt_injection.ValueDict(name="Bob")
    assert d["name"] == "Bob"

def test_valuedict_missing_returns_placeholder():
    d = prompt_injection.ValueDict()
    assert d["missing"] == "{missing}"

# ================ END ValueDict tests =======================


# ================= START inject_values tests ================

def test_inject_values_injects_value():
    smsg = SystemMessage(content="System says {system_info}", inject_prompt=True)
    msg = UserMessage(content="Hello, {name}!", inject_prompt=True)
    history = MessageHistory([smsg, msg])
    value_dict = ValueDict({"name": "Alice", "system_info": "All systems operational"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "System says All systems operational"
    assert result[0].inject_prompt is False
    assert result[1].content == "Hello, Alice!"
    assert result[1].inject_prompt is False

def test_inject_values_ignores_no_inject():
    msg = Message(role=Role.user, content="Hello!", inject_prompt=False)
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello!"
    assert result[0].inject_prompt is False

def test_inject_values_ignores_non_string_content():
    msg = Message(role=Role.user, content=12345, inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == 12345

def test_inject_values_passes_through_unfillable_placeholders():
    """A placeholder that is not a bare key is passed through instead of raising."""
    contents = [
        "{holder.attr}",
        "look at {config.json} please",
        "unbalanced { brace",
        "{name:>20}",
    ]
    history = MessageHistory([UserMessage(content=c, inject_prompt=True) for c in contents])
    value_dict = ValueDict({"holder": _Holder(), "name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    for message, original in zip(result, contents):
        assert message.content == original

# ================ END inject_values tests ==================
