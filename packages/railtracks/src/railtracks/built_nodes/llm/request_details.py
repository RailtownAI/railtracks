from railtracks.llm import Message, MessageHistory, ModelProvider


class RequestDetails:
    """
    A named tuple to store details of each LLM request.
    """

    def __init__(
        self,
        message_input: MessageHistory,
        output: Message | None,
        model_name: str | None,
        model_provider: ModelProvider | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_cost: float | None = None,
        system_fingerprint: str | None = None,
        latency: float | None = None,
    ):
        self.input = message_input
        self.output = output
        self.model_name = model_name
        self.model_provider = model_provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_cost = total_cost
        self.system_fingerprint = system_fingerprint
        self.latency = latency

    def __repr__(self):
        return f"RequestDetails(model_name={self.model_name}, model_provider={self.model_provider}, input={self.input}, output={self.output})"
