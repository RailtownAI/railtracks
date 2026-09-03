# --8<-- [start: exponential_backoff]
import railtracks as rt

exponentialRetry = rt.llm.retries.ExponentialRetry(
    max_tries=5,
    base=2.0,  # delay will be 2^attempt seconds
    jitter=True,  # add random jitter to avoid thundering herd
)
# Now pass in that expoential configuration into your llm. 
rt.llm.OpenAILLM(
    model_name="gpt-4",
    retry_approach=exponentialRetry,
)
# --8<-- [end: exponential_backoff]

# --8<-- [start: make_your_own]
import railtracks as rt

class CustomRetry(rt.llm.retries.RetryApproach):
    @classmethod
    def approach_name(cls) -> str:
        return "custom"

    def _compute_delay(self, attempt: int) -> float:
        # implement your custom retry logic here. For example, you could do a quadratic backoff etc. For more complex logic, please create a new issue or reach out directly to the RailTracks team.
        return 1
# --8<-- [end: make_your_own]
