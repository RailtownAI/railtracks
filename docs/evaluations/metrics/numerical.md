Numerical metrics are key in reporting evaluations that relate to system level results or any other mathematically quantifiable outcomes. In **Railtracks** we mainly use these metrics in the following evaluators:

- [`ToolUseEvaluator`](../evaluators/tool_use_evaluator.md): To report invocation count and failure rate for the tools of an agent.
- [`LLMInferenceEvaluator`](../evaluators/llm_inference_evaluator.md): To report LLM calls and their corresponding usage statistics for agent invocations.