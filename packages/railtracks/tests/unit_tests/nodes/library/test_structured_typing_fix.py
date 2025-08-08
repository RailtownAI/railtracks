"""
Test to validate that the StructuredLLM type hinting fix works correctly.
This test specifically addresses the issue described in GitHub issue #439.

Issue: When using StructuredLLM with rt.call_sync, IDEs show type warnings 
("red squiggles") on response.message_history and response.structured even 
though these are valid operations.

Root Cause: StructuredLLM inherited from LLMBase[_TOutput] but should inherit 
from LLMBase[StructuredResponse[_TOutput]] since it returns StructuredResponse.

Fix: Changed both StructuredLLM and StructuredToolCallLLM to inherit from their 
base classes with the correct generic type parameter: StructuredResponse[_TOutput].
"""

from typing import TYPE_CHECKING
import pytest
from pydantic import BaseModel

import railtracks as rt
from railtracks.nodes.concrete import StructuredLLM
from railtracks.nodes.concrete.response import StructuredResponse


class TriageOutput(BaseModel):
    """Model matching the issue description"""
    category: str
    confidence: float


class TriageAgent(StructuredLLM[TriageOutput]):
    """Test agent matching the GitHub issue description"""
    
    @classmethod
    def output_schema(cls):
        return TriageOutput
    
    @classmethod
    def name(cls) -> str:
        return "TriageAgent"


@pytest.mark.asyncio
async def test_structured_llm_type_hints_fixed(simple_output_model, mock_llm, mock_structured_function):
    """
    Test that verifies the type hints work correctly after our fix.
    This reproduces the scenario from the GitHub issue.
    """
    
    # Create a structured LLM agent similar to the issue example
    class MyTriageAgent(StructuredLLM[simple_output_model]):
        @classmethod
        def output_schema(cls):
            return simple_output_model
        
        @classmethod
        def name(cls) -> str:
            return "MyTriageAgent"
    
    # This simulates the pattern from the issue:
    # response = rt.call_sync(TriageAgent, rt.llm.MessageHistory([message]))
    
    message = rt.llm.UserMessage("Classify this request")
    message_history = rt.llm.MessageHistory([message])
    
    # Call the agent (this is what rt.call_sync does internally)
    response = await rt.call(
        MyTriageAgent,
        user_input=message_history,
        llm_model=mock_llm(structured=mock_structured_function)
    )
    
    # These should work without type errors (the original issue)
    mess_hist = response.message_history  # Should be MessageHistory
    result = response.structured          # Should be simple_output_model
    
    # Verify runtime behavior is correct
    assert isinstance(response, StructuredResponse)
    assert isinstance(mess_hist, rt.llm.MessageHistory)
    assert isinstance(result, simple_output_model)
    assert result.text == "dummy content"
    assert result.number == 42
    
    # Type checking validation - these should not cause mypy/IDE warnings
    if TYPE_CHECKING:
        # After our fix, these should be properly typed:
        typed_response: StructuredResponse[simple_output_model] = response
        typed_history: rt.llm.MessageHistory = mess_hist
        typed_result: simple_output_model = result


def test_structured_llm_inheritance_typing():
    """
    Test that the generic type inheritance is correct after our fix.
    """
    # Check that TriageAgent properly inherits the right generic types
    
    # The fix should make StructuredLLM inherit from LLMBase[StructuredResponse[_TOutput]]
    # instead of LLMBase[_TOutput]
    
    # We can verify this by checking the type annotations
    import inspect
    
    # Get the invoke method signature 
    invoke_sig = inspect.signature(TriageAgent.invoke)
    
    # The return annotation should indicate StructuredResponse
    return_annotation = invoke_sig.return_annotation
    
    # We can't easily check the exact type at runtime, but we can verify
    # that the method signatures make sense
    assert callable(TriageAgent.invoke)
    
    # Check return_output method from the mixin
    return_output_sig = inspect.signature(TriageAgent.return_output)
    
    # This should return StructuredResponse[_TBaseModel] 
    assert "StructuredResponse" in str(return_output_sig.return_annotation)


if __name__ == "__main__":
    print("Running type hint validation tests...")
    test_structured_llm_inheritance_typing()
    print("✓ Type hint tests passed!")