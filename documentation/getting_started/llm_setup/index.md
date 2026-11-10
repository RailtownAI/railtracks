# LLM Setup

Railtracks is model-agnostic; you can use any major cloud LLM provider or run a model locally. This page covers how to configure access to whichever LLM you choose.

______________________________________________________________________

## Cloud Providers

Most LLM providers (OpenAI, Anthropic, Google, etc.) require an **API key** to authenticate your requests.

What is an API key?

An API key is a secret token that identifies your account when making requests to a provider's service. Treat it like a password, don't commit it to version control or share it publicly.

When you sign up with a provider, they'll give you an API key from their dashboard. You then make that key available to Railtracks as an environment variable.

### Setting your API key

The recommended way is to store keys in a `.env` file at the root of your project:

.env

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

Then load it at the top of your script:

```python
from dotenv import load_dotenv
load_dotenv()
```

Never commit your `.env` file

Add `.env` to your `.gitignore` to make sure your keys aren't accidentally pushed to a repository.

.gitignore

```bash
.env
```

Alternatively, you can set environment variables directly in your shell:

```bash
export OPENAI_API_KEY=sk-...
```

```powershell
$env:OPENAI_API_KEY="sk-..."
```

Each provider uses a different environment variable name. See the [Supported Providers](https://docs.railtracks.org/integrations/llms/providers/index.md) page for the full list.

______________________________________________________________________

## Local Models

If you prefer to run models locally (no API key required, no data leaving your machine), Railtracks supports local inference through compatible backends.

Common options include:

- **[Ollama](https://ollama.com/)**: run open-source models like Llama, Mistral, and Gemma locally with a one-line command
  - Railtracks has direct support for Ollama:
  - Also can connect to it using `OpenAICompatibleProvider`
- **[LM Studio](https://lmstudio.ai/)**: a desktop app for downloading and running local models with an OpenAI-compatible API
  - Exposes a local HTTP server that Railtracks can connect to via the `OpenAICompatibleProvider`.

LLM Support

For implementation details head on to [Providers](https://docs.railtracks.org/integrations/llms/platforms/index.md).

______________________________________________________________________

## Choosing a Provider

Not sure which to use? A few pointers:

| Situation                   | Recommendation                                           |
| --------------------------- | -------------------------------------------------------- |
| Getting started quickly     | OpenAI (`gpt-6-luna`) or Anthropic (`claude-sonnet-5-5`) |
| Privacy-sensitive / offline | Ollama with a local model                                |
| Cost-sensitive at scale     | Check per-token pricing on each provider's site          |
| Need multimodal (vision)    | OpenAI, Anthropic, or Gemini                             |

For a full breakdown of supported providers and how to configure each one, see [Supported Providers](https://docs.railtracks.org/integrations/llms/providers/index.md).

______________________________________________________________________

## Testing without an API key

`EchoLLM` is an offline model for tests and local examples. Constructing it and calling it needs no API key and no network access. Pass it to an [agent node](https://docs.railtracks.org/documentation/agent_design/overview/#agent-node) the same way you would pass any other model, then run that agent through a [Flow](https://docs.railtracks.org/documentation/invocation/flows/index.md).

On every chat call the model returns one assistant message: the full message history it received, one message per line in each message's `str()` form (`role: content`), then a final line that reads `This is an echo of the test model.` It never requests a tool call, so an agent that has tools finishes in a single turn and the reply is still that echo. The async methods return the same text as the sync ones. [Structured output](https://docs.railtracks.org/documentation/agent_design/structured_extraction/index.md) is not supported; `structured` and `astructured` raise `NotImplementedError` with the message `EchoLLM does not support structured output.`

```python
import railtracks as rt

agent = rt.agent_node(
    llm=rt.llm.EchoLLM(),
    system_message="You are a helper",
)

flow = rt.Flow("Echo example", entry_point=agent)
result = flow.invoke("hi")
print(result.content)
```

Running that example prints:

```text
system: You are a helper
user: hi
This is an echo of the test model.
```

The response reports zero input tokens, zero output tokens, zero cost, and zero latency, and the model name is `echo`.
