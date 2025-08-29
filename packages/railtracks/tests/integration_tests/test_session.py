import pytest
import pytest
import railtracks as rt
import asyncio


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
    result = asyncio.run(decorated_function())
    assert result == "async result"

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
    
    result = asyncio.run(decorated_function())
    assert result == "context accessed"

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
    
    result = asyncio.run(decorated_function())
    assert result == "completed"

def test_session_decorator_sync_function_validation():
    """Test that using @rt.session on sync function raises appropriate error."""
    import pytest
    
    with pytest.raises(TypeError, match="@session decorator can only be applied to async functions"):
        @rt.session()
        def sync_function():
            return "this should fail"

# ================ END Session: Decorator Integration Tests ===============


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
    result = asyncio.run(decorated_function())
    assert result == "async result"

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
    
    result = asyncio.run(decorated_function())
    assert result == "context accessed"

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
    
    result = asyncio.run(decorated_function())
    assert result == "completed"

def test_session_decorator_sync_function_validation():
    """Test that using @rt.session on sync function raises appropriate error."""
    import pytest
    
    with pytest.raises(TypeError, match="@session decorator can only be applied to async functions"):
        @rt.session()
        def sync_function():
            return "this should fail"

# ================ END Session: Decorator Integration Tests ===============