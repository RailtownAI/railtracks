from src.requestcompletion.llm.models.local.ollama import Ollama
from src.requestcompletion.llm import (
    MessageHistory,
    UserMessage,
    SystemMessage,
)
import requestcompletion as rc

MODEL_NAME = "ollama_chat/llama3.2:latest"

def get_todays_date(tell_time: bool):
    """
    Returns the correct date once called. Time can also be provided

    Args:
        tell_time (bool): if set to True will also return time
    """
    import datetime

    if tell_time:
        return str(datetime.datetime.now())
    else:
        return str(datetime.date.today())

DateAgent = rc.library.tool_call_llm(
    pretty_name="Date Agent",
    system_message=SystemMessage("You are an agent capable of telling date and time"),
    model = Ollama(MODEL_NAME),
    connected_nodes={
        rc.nodes.library.from_function(get_todays_date)
    }
)

with rc.Runner() as runner:
    result = runner.run_sync(DateAgent, message_history=MessageHistory([UserMessage("What is today's date and current time?")]))

print(result.answer)