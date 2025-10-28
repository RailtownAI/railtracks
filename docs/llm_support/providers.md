# Supported Providers
We currently support connecting to different available LLMs through the following providers:

- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Cohere** - Cohere models
- **Gemini** - Google's Gemini models
- **Azure AI Foundry** - Azure-hosted models
- **Ollama** - Local and self-hosted models
- **HuggingFace** - HuggingFace Serverless Inference models
- **Portkey** - Use your portkey to connect to any of their supported models

This allows you to use the same codebase to interact with different LLMs, making it easy to switch providers or use multiple providers in parallel, completely abstracting the underlying API differences.

Take a look at the examples below to see how using different providers look for achieving the same task.

## Quick Start Examples

=== "OpenAI"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `OPENAI_API_KEY`
    
    ```python
    --8<-- "docs/scripts/providers.py:open_ai"
    ```

=== "Anthropic"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `ANTHROPIC_API_KEY`

    ```python
    --8<-- "docs/scripts/providers.py:anthropic"
    ```

=== "Cohere"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, RailTracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `COHERE_API_KEY`
    
    ```python
    --8<-- "docs/scripts/providers.py:cohere"
    ```

=== "Gemini"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `GEMINI_API_KEY`

    ```python
    --8<-- "docs/scripts/providers.py:gemini"
    ```

=== "Portkey"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `PORTKEY_API_KEY`

    ```python 
    --8<-- "docs/scripts/providers.py:portkey"
    ```

=== "Any OpenAI Comptabile Endpoint"
    Do you have an OpenAI comptaible endpoint you want to use. You can use it with Railtracks. 

    !!! warning "API Token"
        You will have to pass in your API token manually

    ```python
    --8<-- "docs/scripts/providers.py:openaicompat"
    ```




=== "Azure AI Foundry"

    ```python
    --8<-- "docs/scripts/providers.py:azure"
    ```

=== "Ollama"

    ```python
    --8<-- "docs/scripts/providers.py:ollama"
    ```

=== "HuggingFace"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `HF_TOKEN`

    !!! caution "Tool Calling Support"
        For HuggingFace serverless inference models, you need to make sure that the model you are using supports tool calling. We **DO NOT**  check for tool calling support in HuggingFace models. If you are using a model that does not support tool calling, it will default to regular chat, even if the `tool_nodes` parameter is provided.

    In case of HuggingFace, `model_name` must be of the format:

    - `huggingface/<provider>/<hf_org_or_user>/<hf_model>`
    - `<provider>/<hf_org_or_user>/<hf_model>`"

    Here are a few example models that you can use:

    ```python
    --8<-- "docs/scripts/providers.py:huggingface_models"
    ```

    ```python
    --8<-- "docs/scripts/providers.py:huggingface"
    ```

=== "Telus"
    !!! info "Environment Variables Configuration"
        Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the `dotenv` framework to load environment variables from a `.env` file.
        Variable name for the API key: `TELUS_API_KEY`

    This support is coming soon.

```python
--8<-- "docs/scripts/providers.py:to_agent"
```

!!! info "Tool Calling Capabilities"
    If you want to use tool calling capabilities by passing the `tool_nodes` parameter to the `agent_node`, you can do so with any of the above providers. However, you need to ensure that the provider and the specific LLM model you are using support tool calling.


## Writing Custom LLM Providers
We hope to cover most of the common and widely used LLM providers, but if you need to use a provider that is not currently supported, you can implement your own LLM provider by subclassing `LLMProvider` and implementing the required methods. 

For our implementation, we have benefited from the amazing [LiteLLM](https://github.com/BerriAI/litellm) framework, which provides excellent multi-provider support.

!!! tip "Custom Provider Documentation"
    Please check out the `llm` module for more details on how to build a integration.

