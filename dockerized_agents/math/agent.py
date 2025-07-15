def main(*args, **kwargs):
    import requestcompletion as rc
    from requestcompletion.nodes.library import tool_call_llm

    # ================= Tools =================
    @rc.to_node
    def add(x: int, y: int) -> int:
        return x + y

    @rc.to_node
    def multiply(x: int, y: int) -> int:
        return x * y

    @rc.to_node
    def subtract(x: int, y: int) -> int:
        return x - y

    @rc.to_node
    def divide(x: int, y: int) -> int:
        if y == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return x / y

    # =========================================

    agent = tool_call_llm(
        connected_nodes={add, multiply, subtract, divide},
        system_message="""You are a math genius with access to the following tools:
        - add: add two numbers
        - multiply: multiply two numbers
        - subtract: subtract two numbers
        - divide: divide two numbers
        """,
        model=rc.llm.OpenAILLM("gpt-4o"),
    )

    user_prompt = """Solve the following math expression using your tools: 5 + 3 * 2"""
    message_history = rc.llm.MessageHistory()
    message_history.append(rc.llm.UserMessage(user_prompt))

    with rc.Runner() as run:
        result = run.run_sync(agent, message_history)

    print(result.answer.content)
