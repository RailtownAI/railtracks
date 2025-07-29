from railtracks.llm import OpenAILLM


def test_llm_correct_init():
    """
    Test that OpenAI initializes correctly with a valid model name.
    """
    model = OpenAILLM("gpt-4o")
    assert model is not None
