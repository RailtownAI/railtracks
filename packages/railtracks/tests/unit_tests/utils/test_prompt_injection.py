from railtracks.llm import Message, MessageHistory, SystemMessage, UserMessage
from railtracks.llm.message import Role
from railtracks.llm.prompt_injection_utils import KeyOnlyFormatter, ValueDict
from railtracks.utils import prompt_injection

# ================= START KeyOnlyFormatter tests ============


def test_formatter_uses_only_kwargs():
    f = KeyOnlyFormatter()
    formatted = f.format("Hello, {name}", name="Test")
    assert formatted == "Hello, Test"


def test_formatter_missing_key_returns_placeholder():
    f = KeyOnlyFormatter()
    formatted = f.format("Hello, {name}")
    assert formatted == "Hello, {name}"


def test_formatter_leaves_literal_braces_unchanged():
    f = KeyOnlyFormatter()
    formatted = f.format("We define {x. some property} and note {a, b}.", x="VALUE")
    assert formatted == "We define {x. some property} and note {a, b}."


def test_formatter_leaves_malformed_braces_unchanged():
    f = KeyOnlyFormatter()
    formatted = f.format("We define {x.", x="VALUE")
    assert formatted == "We define {x."


def test_formatter_ignores_attribute_and_index_fields():
    f = KeyOnlyFormatter()
    formatted = f.format("Values: {name.upper} {name[0]}", name="Alice")
    assert formatted == "Values: {name.upper} {name[0]}"


def test_formatter_preserves_escaped_braces():
    f = KeyOnlyFormatter()
    formatted = f.format("Literal {{name}} and injected {name}", name="Alice")
    assert formatted == "Literal {name} and injected Alice"


# ================ END KeyOnlyFormatter tests ===============


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


def test_inject_values_does_not_crash_on_literal_braces():
    msg = UserMessage(
        content="We define the set {x. some property} and note (e.g. {a, b}).",
        inject_prompt=True,
    )
    history = MessageHistory([msg])
    value_dict = ValueDict({"x": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert (
        result[0].content
        == "We define the set {x. some property} and note (e.g. {a, b})."
    )
    assert result[0].inject_prompt is False


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


def test_inject_values_catches_valueerror(monkeypatch):
    # Patch fill_prompt to throw ValueError
    msg = Message(role=Role.user, content="Hello, {name}!", inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    monkeypatch.setattr(
        UserMessage,
        "fill_prompt",
        lambda content, vd: (_ for _ in ()).throw(ValueError("forced")),
    )

    # Should not raise, and content should be unchanged
    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello, {name}!"


# ================ END inject_values tests ==================
