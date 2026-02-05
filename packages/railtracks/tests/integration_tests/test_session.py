import pytest
import pytest
import railtracks as rt
import asyncio
from pathlib import Path


def example_1():
    return "hello world"



def example_2():
    return "goodbye world"


E1 = rt.function_node(example_1)
E2 = rt.function_node(example_2)

@pytest.mark.asyncio
async def test_multiple_sessions_ids_distinct():
    with rt.Session() as sess1:
        await rt.call(E1)
        await rt.call(E1)

    with rt.Session() as sess2:
        await rt.call(E2)

    assert sess1._identifier != sess2._identifier, (
        "Session identifiers should be distinct"
    )

# ================= START Session: Decorator Integration Tests ===============

def test_session_decorator_with_rt_call():
    """Test session decorator with actual rt.call operations."""
    @rt.function_node
    async def async_example():
        return "async result"
    
    @rt.session(timeout=5)
    async def decorated_function():
        result = await rt.call(async_example)
        return result
    
    # Run the decorated function
    result, session_obj = asyncio.run(decorated_function())
    assert result == "async result"
    assert isinstance(session_obj, rt.Session)

def test_session_decorator_with_custom_context():
    """Test session decorator passes context correctly."""
    @rt.function_node
    def context_reader():
        # This would read from context in real usage
        return "context accessed"
    
    @rt.session(context={"test_key": "test_value"})
    async def decorated_function():
        result = await rt.call(context_reader)
        return result
    
    result, session_obj = asyncio.run(decorated_function())
    assert result == "context accessed"
    assert isinstance(session_obj, rt.Session)

def test_session_decorator_timeout_parameter():
    """Test session decorator respects timeout parameter."""
    @rt.function_node
    async def slow_function():
        await asyncio.sleep(0.1)  # Short delay
        return "completed"
    
    @rt.session(timeout=1)  # Generous timeout
    async def decorated_function():
        result = await rt.call(slow_function)
        return result
    
    result, session_obj = asyncio.run(decorated_function())
    assert result == "completed"
    assert isinstance(session_obj, rt.Session)

def test_session_decorator_sync_function_validation():
    """Test that using @rt.session on sync function raises appropriate error."""
    import pytest
    
    with pytest.raises(TypeError, match="@session decorator can only be applied to async functions"):
        @rt.session()
        def sync_function():
            return "this should fail"

def test_session_decorator_vs_context_manager():
    """Test demonstrating the difference between decorator and context manager usage."""
    @rt.function_node
    def sample_node():
        return "sample result"
    
    # Using context manager - session available during execution
    async def context_manager_workflow():
        with rt.Session(name="cm-session") as session:
            result = await rt.call(sample_node)
            # Session object is available here during execution
            session_name_during = session.name
            return result, session_name_during
    
    # Using decorator - session available after execution  
    @rt.session(name="dec-session")
    async def decorator_workflow():
        result = await rt.call(sample_node)
        # Session object is NOT available here during execution
        # It will be returned as part of the tuple
        return result
    
    # Test context manager
    cm_result, cm_session_name = asyncio.run(context_manager_workflow())
    assert cm_result == "sample result"
    assert cm_session_name == "cm-session"
    
    # Test decorator
    dec_result, dec_session = asyncio.run(decorator_workflow()) 
    assert dec_result == "sample result"
    assert dec_session.name == "dec-session"
    
    # Verify different approaches yield expected results
    assert cm_result == dec_result
    assert cm_session_name != dec_session.name

def test_session_decorator_tuple_handling():
    """Test that session decorator properly handles functions returning tuples."""
    @rt.function_node
    def tuple_returning_node():
        return "hello", 42, True
    
    @rt.session()
    async def function_returning_tuple():
        result = await rt.call(tuple_returning_node)
        # Return the tuple directly
        return result
    
    @rt.session()
    async def function_returning_multiple_values():
        result = await rt.call(tuple_returning_node)
        # Unpack and return as separate values (creates a new tuple)
        val1, val2, val3 = result
        return val1, val2, val3
    
    # Test 1: Function that returns a tuple from a node call
    result1, session1 = asyncio.run(function_returning_tuple())
    assert result1 == ("hello", 42, True)
    assert isinstance(session1, rt.Session)
    
    # The original tuple structure is preserved
    assert len(result1) == 3
    assert result1[0] == "hello"
    assert result1[1] == 42
    assert result1[2] == True
    
    # Test 2: Function that creates and returns a tuple
    result2, session2 = asyncio.run(function_returning_multiple_values())
    assert result2 == ("hello", 42, True)
    assert isinstance(session2, rt.Session)
    
    # Both should have the same result but different sessions
    assert result1 == result2
    assert session1._identifier != session2._identifier


def test_session_save_file_uses_flow_name_precedence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with rt.Session(flow_name="flow-priority", name="session-name") as session_obj:
        pass

    sessions_dir = tmp_path / ".railtracks" / "data" / "sessions"
    saved_files = list(sessions_dir.glob("*.json"))

    assert len(saved_files) == 1
    assert saved_files[0].name.startswith("flow-priority_")
    assert session_obj._identifier in saved_files[0].name


def test_session_save_file_falls_back_to_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with rt.Session(name="session-only") as session_obj:
        pass

    sessions_dir = tmp_path / ".railtracks" / "data" / "sessions"
    saved_files = list(sessions_dir.glob("*.json"))

    assert len(saved_files) == 1
    assert saved_files[0].name.startswith("session-only_")
    assert session_obj._identifier in saved_files[0].name


def test_session_payload_callback_called_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    payloads = []

    def payload_handler(payload):
        payloads.append(payload)

    with rt.Session(payload_callback=payload_handler, save_state=False) as session_obj:
        pass

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["session_id"] == session_obj._identifier
    assert "runs" in payload
    assert payload["runs"] == []


def test_session_payload_callback_runs_on_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    payloads = []

    def payload_handler(payload):
        payloads.append(payload)

    with pytest.raises(RuntimeError, match="boom"):
        with rt.Session(payload_callback=payload_handler, save_state=False):
            raise RuntimeError("boom")

    assert len(payloads) == 1


def test_session_payload_includes_flow_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    payloads = []

    def payload_handler(payload):
        payloads.append(payload)

    with rt.Session(
        flow_name="flow-name",
        flow_id="flow-123",
        payload_callback=payload_handler,
        save_state=False,
    ) as session_obj:
        pass

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["flow_id"] == "flow-123"
    assert payload["flow_name"] == "flow-name"
    assert payload["session_id"] == session_obj._identifier


def test_session_payload_flow_id_defaults_to_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    payloads = []

    def payload_handler(payload):
        payloads.append(payload)

    with rt.Session(payload_callback=payload_handler, save_state=False):
        pass

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["flow_id"] is None

# ================ END Session: Decorator Integration Tests ===============