We currently support connecting to different available LLMs through the following providers:

- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Gemini** - Google's Gemini models

Take a look at the examples below to see how using different providers look for achieving the same task.

```python
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.OpenAILLM("gpt-6-luna")
```

```python
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.AnthropicLLM("claude-sonnet-5-5")
```

```python
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.GeminiLLM(model_name="gemini-3.8-flash")
```

Environment Variables Configuration

Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the [`python-dotenv`](https://pypi.org/project/python-dotenv/) framework to load environment variables from a `.env` file.
