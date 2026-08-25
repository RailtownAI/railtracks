from railtracks.llm._exceptions import RTError

# `RTError` is defined in the `llm` package because that package must stay free of
# imports from the rest of `railtracks`, and `LLMError` needs the same base class.
__all__ = ["RTError"]
