from railtracks.llm import AnthropicLLM

def test_llm_correct_init():
    """
    Test that AnthropicLLM initializes correctly with a valid model name.
    """
    model = AnthropicLLM("claude-3-5-sonnet-20240620")
    assert model is not None
