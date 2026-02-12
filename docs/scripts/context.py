# --8<-- [start: context_basics]
import railtracks as rt

# Set up some context data
data = {"var_1": "value_1"}

@rt.function_node
async def my_workflow():
    value1 = rt.context.get("var_1")  # Outputs: value_1
    value2 = rt.context.get("var_2", "default_value")  # Outputs: default_value

    rt.context.put("var_2", "value_2")  # Sets var_2 to value_2
    rt.context.put("var_1", "new_value_1")  # Replaces var_1 with new_value_1
    return value1

# Create and run a Flow
flow = rt.Flow("Context Example", entry_point=my_workflow, context=data)
# --8<-- [end: context_basics]

# --8<-- [start: context_in_node]
import railtracks as rt

@rt.function_node
def some_node():
    return rt.context.get("var_1")

@rt.function_node
async def main():
    result = await rt.call(some_node)
    return result

flow = rt.Flow("Context in Node", entry_point=main, context={"var_1": "value_1"})
# --8<-- [end: context_in_node]

def get_issue_from_input(input: str) -> str:
    # Dummy implementation for example purposes
    return "ISSUE-123"

def comment_on_github_issue(issue: str, comment: str):
    # Dummy implementation for example purposes
    print(f"Commented on {issue}: {comment}")

# --8<-- [start: example]
import railtracks as rt

# Define a tool that uses context
@rt.function_node
def find_issue(input: str) -> str:
    issue = get_issue_from_input(input)  # Assume this function finds an issue number from the inpu
    rt.context.put("issue_number", issue)
    return issue

@rt.function_node
def comment_on_issue(comment: str):
    try:
        issue = rt.context.get("issue_number")
    except KeyError:
        return "No relevant issue is available."
    
    comment_on_github_issue(issue, comment)  # Assume this function comments on the issue

# Define the agent with the tool
GitHubAgent = rt.agent_node(
    tool_nodes=[find_issue, comment_on_issue],
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are an agent that provides information based on important facts.",
)

# Run the agent
@rt.function_node
async def gh_agent():
    response = await rt.call(
        GitHubAgent,
        "What is the last issue created? Please write a comment on it."
    )
    return response

flow = rt.Flow("GitHub Agent", entry_point=gh_agent)
# --8<-- [end: example]
