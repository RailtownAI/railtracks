# 🌐 Supported Providers
We currently support connecting to different available LLMs through the following providers:

- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Gemini** - Google's Gemini models
- **Azure AI Foundry** - Azure-hosted models
- **Ollama** - Local and self-hosted models
- **HuggingFace** - HuggingFace Serverless Inference models

This allows you to use the same codebase to interact with different LLMs, making it easy to switch providers or use multiple providers in parallel, completely abstracting the underlying API differences.

Take a look at the examples below to see how using different providers look for achieving the same task.

## 📋 Quick Start Examples

=== "OpenAI"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, RailTracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `OPENAI_API_KEY`
    
    ```python
    import railtracks as rt
    from dotenv import load_dotenv
    _ = load_dotenv()

    model = rt.llm.OpenAILLM("gpt-4o")
    ```

=== "Anthropic"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, RailTracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `ANTHROPIC_API_KEY`

    ```python
    import railtracks as rt
    from dotenv import load_dotenv
    _ = load_dotenv()

    model = rt.llm.AnthropicLLM("claude-sonnet-4")
    ```

=== "Gemini"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, RailTracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `GEMINI_API_KEY`

    ```python
    import railtracks as rt
    from dotenv import load_dotenv
    _ = load_dotenv()

    model = rt.llm.GeminiLLM("gemini-2.5-flash")
    ```

=== "Azure AI Foundry"

    ```python
    import railtracks as rt
    from dotenv import load_dotenv
    _ = load_dotenv()

    model = rt.llm.AzureAILLM("azure_ai/deepseek-r1")
    ```

=== "Ollama"

    ```python
    import railtracks as rt
    from dotenv import load_dotenv
    _ = load_dotenv()

    model = rt.llm.OllamaLLM("deepseek-r1:8b"),
    ```

=== "HuggingFace"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, RailTracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `HF_TOKEN`

    !!! caution "Tool Calling Support"
        For HuggingFace serverless inference models, you need to make sure that the model you are using supports tool calling. We **DO NOT**  check for tool calling support in HuggingFace models. If you are using a model that does not support tool calling, it will default to regular chat, even if the `tool_nodes` parameter is provided.

    In case of HuggingFace, `model_name` must be of the format:  <br>
    - `huggingface/<provider>/<hf_org_or_user>/<hf_model>` or  <br>
    - `<provider>/<hf_org_or_user>/<hf_model>`"  <br>
    Here are a few example models that you can use:
    ```python
    # same model, different provider: both have tool calling support
    rt.llm.HuggingFaceLLM("together_ai/meta-llama/Llama-3.3-70B-Instruct") 
    rt.llm.HuggingFaceLLM("sambanova/meta-llama/Llama-3.3-70B-Instruct")

    # does not support tool calling
    rt.llm.HuggingFaceLLM("featherless-ai/mistralai/Mistral-7B-Instruct-v0.2")
    ```

    ```python
    import railtracks as rt
    from dotenv import load_dotenv
    _ = load_dotenv()

    model = rt.llm.HuggingFaceLLM("together/deepseek-ai/DeepSeek-R1")
    ```

```python
GeneralAgent = rt.agent_node(
    llm=model,
    system_message="You are a general-purpose AI assistant."
)
```

!!! info "Tool Calling Capabilities"
    If you want to use tool calling capabilities by passing the `tool_nodes` parameter to the `agent_node`, you can do so with any of the above providers. However, you need to ensure that the provider and the specific LLM model you are using support tool calling.


## 🔧 Writing Custom LLM Providers
We hope to cover most of the common and widely used LLM providers, but if you need to use a provider that is not currently supported, you can implement your own LLM provider by subclassing `LLMProvider` and implementing the required methods. 

For our implementation, we have benefited from the amazing [LiteLLM](https://github.com/BerriAI/litellm) 🚀 framework, which provides excellent multi-provider support.

!!! tip "Custom Provider Documentation"
    Please refer to the **Custom LLM Provider documentation** for detailed instructions on how to implement your own provider.

