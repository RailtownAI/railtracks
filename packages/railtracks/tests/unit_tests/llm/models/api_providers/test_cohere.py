from railtracks.llm import CohereLLM 


def test_llm_correct_init():
    """
    Test that Cohere initializes correctly with a valid model name.
    """
    model = CohereLLM("command-a-03-2025")
    assert model is not None