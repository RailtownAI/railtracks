We currently support connecting to different available LLMs through the following providers:

- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Gemini** - Google's Gemini models

Take a look at the examples below to see how using different providers look for achieving the same task.

=== "OpenAI"
    
    ```python
    --8<-- "docs/scripts/providers.py:open_ai"
    ```

=== "Anthropic"

    ```python
    --8<-- "docs/scripts/providers.py:anthropic"
    ```

=== "Gemini"

    ```python
    --8<-- "docs/scripts/providers.py:gemini"
    ```
    
??? info "Environment Variables Configuration"
    Make sure you set the appropriate environment variable keys for your specific provider. By default, Railtracks uses the [`python-dotenv`](https://pypi.org/project/python-dotenv/) framework to load environment variables from a `.env` file.
