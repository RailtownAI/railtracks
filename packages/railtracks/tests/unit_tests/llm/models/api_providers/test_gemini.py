from railtracks.llm import GeminiLLM

def test_llm_correct_init():
    """
    Test that GeminiLLM initializes correctly with a valid model name.
    """
    model = GeminiLLM("gemini-2.5-flash")
    assert model is not None
