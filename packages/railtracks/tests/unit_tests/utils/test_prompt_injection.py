import pytest
from railtracks.utils import prompt_injection
from railtracks.llm import Message, MessageHistory

# ================= START KeyOnlyFormatter tests ============

def test_formatter_uses_only_kwargs():
    f = prompt_injection.KeyOnlyFormatter()
    formatted = f.format("Hello, {name}", name="Test")
    assert formatted == "Hello, Test"

def test_formatter_missing_key_returns_placeholder():
    f = prompt_injection.KeyOnlyFormatter()
    formatted = f.format("Hello, {name}")
    assert formatted == "Hello, {name}"

# ================ END KeyOnlyFormatter tests ===============


# ================= START ValueDict tests ====================

def test_valuedict_returns_value_if_exists():
    d = prompt_injection.ValueDict(name="Bob")
    assert d["name"] == "Bob"

def test_valuedict_missing_returns_placeholder():
    d = prompt_injection.ValueDict()
    assert d["missing"] == "{missing}"

# ================ END ValueDict tests =======================


# ================= START fill_prompt tests ==================

def test_fill_prompt_fills_placeholders():
    value_dict = prompt_injection.ValueDict({"name": "Alice"})
    result = prompt_injection.fill_prompt("Hi {name}!", value_dict)
    assert result == "Hi Alice!"

def test_fill_prompt_missing_key():
    value_dict = prompt_injection.ValueDict()
    result = prompt_injection.fill_prompt("Hi {missing}!", value_dict)
    assert result == "Hi {missing}!"

# ================ END fill_prompt tests =====================


# ================= START inject_values tests ================

def test_inject_values_injects_value():
    msg = Message(role="user", content="Hello, {name}!", inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = prompt_injection.ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello, Alice!"
    assert result[0].inject_prompt is False

def test_inject_values_ignores_no_inject():
    msg = Message(role="user", content="Hello!", inject_prompt=False)
    history = MessageHistory([msg])
    value_dict = prompt_injection.ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello!"
    assert result[0].inject_prompt is False

def test_inject_values_ignores_non_string_content():
    msg = Message(role="user", content=12345, inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = prompt_injection.ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == 12345

def test_inject_values_catches_valueerror(monkeypatch):
    # Patch fill_prompt to throw ValueError
    msg = Message(role="user", content="Hello, {name}!", inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = prompt_injection.ValueDict({"name": "Alice"})

    monkeypatch.setattr(prompt_injection, "fill_prompt", lambda content, vd: (_ for _ in ()).throw(ValueError("forced")))

    # Should not raise, and content should be unchanged
    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello, {name}!"

# ================ END inject_values tests ==================