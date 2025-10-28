import railtracks as rt
model: rt.llm.ModelBase
# --8<-- [start: open_ai]
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.OpenAILLM("gpt-4o")
# --8<-- [end: open_ai]

# --8<-- [start: anthropic]
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.AnthropicLLM("claude-sonnet-4")
# --8<-- [end: anthropic]

# --8<-- [start: cohere]
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.CohereLLM("command-a-03-2025")
# --8<-- [end: cohere]

# --8<-- [start: gemini]
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

model = rt.llm.GeminiLLM("gemini-2.5-flash")
# --8<-- [end: gemini]

# --8<-- [start: azure]
import railtracks as rt
# make sure to configure your environment variables for Azure AI

model = rt.llm.AzureAILLM("azure_ai/deepseek-r1")
# --8<-- [end: azure]

# --8<-- [start: portkey]
import railtracks as rt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file under PORTKEY_API_KEY

# using gpt through Portkey
model = rt.llm.PortKeyLLM("@<your opennai slug>/gpt-4o")
# using claude through Portkey
model = rt.llm.PortKeyLLM("@<your anthropic slug>/claude-sonnet-4-5-20250929")
# --8<-- [end: portkey]

# --8<-- [start: openaicompat]
import railtracks as rt

# you can pass in the model name, api endpoint and your API key to connect to your LLM
model = rt.llm.OpenAICompatibleProvider("<your model name>", api_base="<base api url>", api_key="<api key>")
# --8<-- [end: openaicompat]

# --8<-- [start: ollama]
import railtracks as rt
# make sure to configure your environment variables for Ollama

model = rt.llm.OllamaLLM("deepseek-r1:8b")
# --8<-- [end: ollama]

# --8<-- [start: huggingface_models]
rt.llm.HuggingFaceLLM("together_ai/meta-llama/Llama-3.3-70B-Instruct") 
rt.llm.HuggingFaceLLM("sambanova/meta-llama/Llama-3.3-70B-Instruct")

# does not support tool calling
rt.llm.HuggingFaceLLM("featherless-ai/mistralai/Mistral-7B-Instruct-v0.2")
# --8<-- [end: huggingface_models]


# --8<-- [start: huggingface]
import railtracks as rt
# make sure to configure your environment variables for HuggingFace

model = rt.llm.HuggingFaceLLM("together/deepseek-ai/DeepSeek-R1")
# --8<-- [end: huggingface]

# --8<-- [start: to_agent]
# Insert the model you want to use in your agent.
GeneralAgent = rt.agent_node(
    llm=model,
    system_message="You are a helpful AI assistant.",
)
# --8<-- [end: to_agent]



