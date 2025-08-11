from railtracks.llm import HuggingFaceLLM

def test_llm_correct_init():
    """
    Test that HuggingFaceLLM initializes correctly with a valid model name.
    """
    model = HuggingFaceLLM("sambanova/meta-llama/Llama-3.3-70B-Instruct")
    assert model is not None

