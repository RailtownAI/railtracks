Platforms allow connecting to LLMs from different providers through a single API. Railtracks has support for connecting to the following major LLM platforms:

- **Azure AI Foundry**
- **Ollama**
- **HuggingFace**
- **Portkey**
- **Apple Foundation Model** (on-device, macOS 26+ Apple Silicon)

The code remains the same as [LLM Providers](https://docs.railtracks.org/integrations/llms/providers/index.md) with the provider name being replaced with the platform name.

## Quick Start Examples

```python
import railtracks as rt
# Railtracks loads .env automatically; set AZURE_API_BASE and AZURE_API_KEY there.

# Azure OpenAI Service (deployment-routed) — the string after "azure/" is your
# Foundry deployment name and can be anything you chose in the portal.
model = rt.llm.AzureAILLM("azure/my-gpt-5-deployment")

# Azure AI Foundry catalog model (model-routed) — the string after "azure_ai/"
# is a model identifier from Foundry's model catalog.
model = rt.llm.AzureAILLM("azure_ai/deepseek-r1")
```

Environment Variables

Add `AZURE_API_BASE` and `AZURE_API_KEY` to your `.env`. `AZURE_API_BASE` is your Foundry endpoint (e.g. `https://<your-resource>.cognitiveservices.azure.com/`), and `AZURE_API_KEY` is the resource key from the Azure portal.

`AzureAILLM` accepts either litellm prefix, depending on how your model is deployed in Foundry:

- `azure/<deployment>` — Azure OpenAI Service route. The string after the slash is the deployment name you chose in the portal and can be anything (e.g. `azure/my-gpt-5-deployment`).
- `azure_ai/<model>` — Azure AI Foundry model-inference route. The string after the slash is a model identifier from Foundry's catalog (e.g. `azure_ai/deepseek-r1`).

```python
import railtracks as rt
# make sure to configure your environment variables for Ollama

model = rt.llm.OllamaLLM("deepseek-r1:8b")
```

Tool Calling Support

For HuggingFace serverless inference models, you need to make sure that the model you are using supports tool calling. We **DO NOT** check for tool calling support in HuggingFace models. If you are using a model that does not support tool calling, it will default to regular chat, even if the `tool_nodes` parameter is provided.

In case of HuggingFace, `model_name` must be of the format:

- `huggingface/<provider>/<hf_org_or_user>/<hf_model>`
- `<provider>/<hf_org_or_user>/<hf_model>`"

Here are a few example models that you can use:

```python
rt.llm.HuggingFaceLLM("together_ai/meta-llama/Llama-3.3-70B-Instruct") 
rt.llm.HuggingFaceLLM("sambanova/meta-llama/Llama-3.3-70B-Instruct")

# does not support tool calling
rt.llm.HuggingFaceLLM("featherless-ai/mistralai/Mistral-7B-Instruct-v0.2")
```

```python
import railtracks as rt
# make sure to configure your environment variables for HuggingFace

model = rt.llm.HuggingFaceLLM("together/deepseek-ai/DeepSeek-R1")
```

```python
import railtracks as rt

# you can pass in the model name, api endpoint and your API key to connect to your LLM
model = rt.llm.OpenAICompatibleProvider("<your model name>", api_base="<base api url>", api_key="<api key>")
```

```python
import railtracks as rt
# Requires macOS 26+ Apple Silicon with Apple Intelligence enabled.
# Install with `pip install railtracks[apple]`.

model = rt.llm.AppleFMLLM(temperature=0.7)
```

Availability

Runs entirely on-device with no API key. Requires:

- macOS 26.0+ on an Apple Silicon Mac
- Apple Intelligence enabled in System Settings
- Xcode 26.0+ installed, with the Xcode and Apple SDKs licence agreement accepted (open Xcode once after installing)
- Python 3.10+
- Install with `pip install railtracks[apple]`

No tool calling

Apple's on-device SDK drives its own tool-calling loop and exposes no interception hook, so `AppleFMLLM.chat_with_tools()` raises `NotImplementedError`. Use another provider (OpenAI, Anthropic, Ollama) for tool-driven flows. Streaming structured output also raises since the SDK's `stream_response` does not accept guided generation. Use `ainvoke` for buffered structured output on the flow containing the agent.

Usage statistics

The Apple SDK returns no token counts or cost. `MessageInfo` reports `latency` (measured locally) and `model_name`; `input_tokens`, `output_tokens`, `total_cost`, and `system_fingerprint` are `None`. Aggregations over mixed-provider sessions treat Apple runs as "unknown usage". On-device inference is free, but reporting `0.0` would silently conflate "free" with "unknown".
