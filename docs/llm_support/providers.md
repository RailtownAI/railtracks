# 🌐 Supported Providers
We currently support connecting to different available LLMs through the following providers:

- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Gemini** - Google's Gemini models
- **Azure AI Foundry** - Azure-hosted models
- **Ollama** - Local and self-hosted models

This allows you to use the same codebase to interact with different LLMs, making it easy to switch providers or use multiple providers in parallel, completely abstracting the underlying API differences.

## 📋 Quick Start Examples

Take a look at the examples below to see how using different providers look for achieving the same task.

=== "OpenAI"

    ```python
    import railtracks as rt

    GeneralAgent = rt.agent_node(
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
        system_message="You are a general-purpose AI assistant."
    )
    ```

=== "Anthropic"

    ```python
    import railtracks as rt

    GeneralAgent = rt.agent_node(
        llm_model=rt.llm.AnthropicLLM("claude-sonnet-4"),
        system_message="You are a general-purpose AI assistant."
    )
    ```

=== "Gemini"

    ```python
    import railtracks as rt

    GeneralAgent = rt.agent_node(
        llm_model=rt.llm.GeminiLLM("gemini-2.5-flash"),
        system_message="You are a general-purpose AI assistant."
    )
    ```

=== "Azure AI Foundry"

    ```python
    import railtracks as rt

    GeneralAgent = rt.agent_node(
        llm_model=rt.llm.AzureAILLM("azure_ai/deepseek-r1"),
        system_message="You are a general-purpose AI assistant."
    )
    ```

=== "Ollama"

    ```python
    import railtracks as rt

    GeneralAgent = rt.agent_node(
        llm_model=rt.llm.OllamaLLM("deepseek-r1:8b"),
        system_message="You are a general-purpose AI assistant."
    )
    ```

!!! info "API Keys"
    Make sure you set the appropriate environment variable keys for your specific provider. By default, RailTracks uses the `dotenv` framework to load environment variables from a `.env` file. Please refer to the API Reference for each provider to see the required environment variables.

!!! info "Tool Calling Capabilities"
    If you want to use tool calling capabilities by passing the `tool_nodes` parameter to the `agent_node`, you can do so with any of the above providers. However, you need to ensure that the provider and the specific LLM model you are using support tool calling.

## 🔧 Writing Custom LLM Providers
We hope to cover most of the common and widely used LLM providers, but if you need to use a provider that is not currently supported, you can implement your own LLM provider by subclassing `LLMProvider` and implementing the required methods. 

For our implementation, we have benefited from the amazing [LiteLLM](https://github.com/BerriAI/litellm) 🚀 framework, which provides excellent multi-provider support.

!!! tip "Custom Provider Documentation"
    Please refer to the **Custom LLM Provider documentation** for detailed instructions on how to implement your own provider.

