Platforms allow connecting to LLMs from different providers through a single API. Railtracks has support for connecting to the following major LLM platforms:

- **Azure AI Foundry**
- **Ollama**
- **HuggingFace**
- **Portkey**

The code remains the same as [LLM Providers](providers.md) with the provider name being replaced with the platform name.

## Quick Start Examples
=== "Azure AI Foundry"
    ```python
    --8<-- "docs/scripts/providers.py:azure"
    ```

=== "Ollama"
    ```python
    --8<-- "docs/scripts/providers.py:ollama"
    ```
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

=== "Any OpenAI Comptabile Endpoint"    
    ```python
    --8<-- "docs/scripts/providers.py:openaicompat"
    ```