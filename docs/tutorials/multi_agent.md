```python
###Need to update this code for it to reflect the refactoring made to RT

gpt_4o = rt.llm.OpenAILLM("gpt-4o")

class AnswerPrediction(BaseModel):
    quality_answer: bool = Field(..., description="The quality of the answer that was provided by the model.")

system_c_o_t = rt.llm.SystemMessage(
    """You are extremley intellegnt reviewer of information that ponders the provided
    question and context to provide a simple one paragraph plan where you discuss you
    thinking process and how you would go about answering the question, without explictely
    answer the question.""")
system_answer = rt.llm.SystemMessage(
    """You are a helpful assistant that works tirelessly to answer a question using the 
    provided context as a guide to answer the question.""")
system_answer_reviewer = rt.llm.SystemMessage(
    """You are a reviewer of the plan that was provided by the model and will determine
    if the plan is feasible and if it will accomplish the task that was asked of you. 
    Be harsh and clear when the plan is not adequete.""")



COTNode = rt.library.terminal_llm("COT", system_message=system_c_o_t, model=gpt_4o)
AnswerNode = rt.library.terminal_llm("Answerer", system_message=system_answer, model=gpt_4o)
ReviewerNode = rt.library.structured_llm(pretty_name="AnswerReviewer", output_model=AnswerPrediction, system_message=system_answer_reviewer, model=gpt_4o)



async def COTLLM(message_history: rt.llm.MessageHistory, number_trails: int = 4):
    original_message_history = deepcopy(message_history)
    for _ in range(number_trails):
        cot_response = await rt.call(COTNode, message_history=message_history)

        message_history.append(rt.llm.AssistantMessage("My plan:" + cot_response))

        answer_response = await rt.call(ReviewerNode, message_history=message_history)
        if not answer_response.quality_answer:
            continue
        else:
            break
    
    original_message_history.append(rt.llm.UserMessage("Contextual Plan: " + cot_response))
    response = await rt.call(AnswerNode, message_history=original_message_history)

    return cot_response, response

    
ChainOfThought = rt.library.from_function(COTLLM)
```