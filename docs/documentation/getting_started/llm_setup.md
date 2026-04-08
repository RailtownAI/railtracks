# LLM Setup

Railtracks is model-agnostic; you can use any major cloud LLM provider or run a model locally. This page covers how to configure access to whichever LLM you choose.

---

## Cloud Providers

Most LLM providers (OpenAI, Anthropic, Google, etc.) require an **API key** to authenticate your requests.

??? info "What is an API key?"

    An API key is a secret token that identifies your account when making requests to a provider's service. Treat it like a password, don't commit it to version control or share it publicly.

    When you sign up with a provider, they'll give you an API key from their dashboard. You then make that key available to Railtracks as an environment variable.

### Setting your API key

The recommended way is to store keys in a `.env` file at the root of your project:

```bash title=".env"
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

Then load it at the top of your script:

```python
from dotenv import load_dotenv
load_dotenv()
```

!!! warning "Never commit your `.env` file"
    Add `.env` to your `.gitignore` to make sure your keys aren't accidentally pushed to a repository.

    ```bash title=".gitignore"
    .env
    ```

Alternatively, you can set environment variables directly in your shell:

=== "macOS / Linux"

    ```bash
    export OPENAI_API_KEY=sk-...
    ```

=== "Windows"

    ```powershell
    $env:OPENAI_API_KEY="sk-..."
    ```

Each provider uses a different environment variable name. See the [Supported Providers](../../llm_support/providers.md) page for the full list.

---

## Local Models

If you prefer to run models locally (no API key required, no data leaving your machine), Railtracks supports local inference through compatible backends.

Common options include:

- **[Ollama](https://ollama.com/)**: run open-source models like Llama, Mistral, and Gemma locally with a one-line command
    - Railtracks has direct support for Ollama:
    - Also can connect to it using `OpenAICompatibleProvider`
- **[LM Studio](https://lmstudio.ai/)**: a desktop app for downloading and running local models with an OpenAI-compatible API
    - Exposes a local HTTP server that Railtracks can connect to via the `OpenAICompatibleProvider`.

!!! info "LLM Support"
    For implementation details head on to [Providers](../../integrations/llms/platforms.md).

---

## Choosing a Provider

Not sure which to use? A few pointers:

| Situation | Recommendation |
|---|---|
| Getting started quickly | OpenAI (`gpt-5`) or Anthropic (`claude-sonnet-4-6`) |
| Privacy-sensitive / offline | Ollama with a local model |
| Cost-sensitive at scale | Check per-token pricing on each provider's site |
| Need multimodal (vision) | OpenAI, Anthropic, or Gemini |

For a full breakdown of supported providers and how to configure each one, see [Supported Providers](../../integrations/llms/providers.md).
