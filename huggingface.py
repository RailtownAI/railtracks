import railtracks as rt

hf_model = rt.llm.HuggingFaceLLM(model_name="gpt2")
mh = rt.llm.MessageHistory(rt.llm.UserMessage("write code for saying hi from LiteLLM"))

hf_model.chat(mh)
