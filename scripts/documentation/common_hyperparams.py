# --8<-- [start: basic_usage]
import railtracks as rt

llm = rt.llm.OpenAILLM(
    "gpt-4o",
    temperature=0.7,
    top_p=0.9,
    max_tokens=256,
    frequency_penalty=0.2,
    presence_penalty=0.1,
)
# --8<-- [end: basic_usage]

# --8<-- [start: reasoning_effort]
import railtracks as rt

reasoning_llm = rt.llm.OpenAILLM("gpt-5-mini", reasoning_effort="low")
# --8<-- [end: reasoning_effort]

# --8<-- [start: fail_fast]
import railtracks as rt

try:
    # Claude Opus 4.7+ rejects non-default temperature/top_p server-side.
    opus_llm = rt.llm.AnthropicLLM("claude-opus-4-7", temperature=0.5)
except rt.llm.UnsupportedHyperparameterError as e:
    print(e.reason)
    # Model anthropic/claude-opus-4-7 does not support 'temperature' (got temperature=0.5).
# --8<-- [end: fail_fast]
