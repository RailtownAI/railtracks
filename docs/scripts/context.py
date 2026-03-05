# --8<-- [start: context_basics]
import railtracks as rt

# Set up some context data
data = {"var_1": "value_1"}

def some_node():
    rt.context.get("var_1")  # Outputs: value_1
    rt.context.get("var_2", "default_value")  # Outputs: default_value

    rt.context.put("var_2", "value_2")  # Sets var_2 to value_2
    rt.context.put("var_1", "new_value_1")  # Replaces var_1 with new_value_1
    
flow = rt.Flow("context-flow", entry_point=some_node, context=data)
flow.invoke()

# --8<-- [end: context_basics]

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

github_flow = rt.Flow("github-flow", entry_point=GitHubAgent)
response = github_flow.invoke("What is the last issue created? Please write a comment on it.")
# --8<-- [end: example]
