# Serving Railtracks Agents with FastAPI

Railtracks framework makes it incredibly easy to expose your flows and agents as a REST API using FastAPI. Because Railtracks natively relies on Python's `async`/`await` patterns for execution, it integrates seamlessly to FastAPI's async route handlers. This enables you to host your agents in robust web servers for production environments.

In this tutorial, you will learn how to:

* Wrap an agent or flow inside a FastAPI route
* Serve an agent as a REST endpoint
* Connect external services to your railtracks logic

For a full interactive walkthrough with code, be sure to check out our [FastAPI Integration Notebook](../../examples/tutorials/fastapi_agent.ipynb) which runs you through creating and testing the API directly!

## Example: Creating a simple endpoint

Below is a quick example mapping out how simple it is to combine FastAPI's `FastAPI()` app with a `rt.Flow`.

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import railtracks as rt

# 1. Define your functionality as usual
@rt.function_node
def calculator_tool(expression: str) -> str:
    """Evaluates a math expression."""
    try:
        # NOTE: Do avoid using eval in production
        return str(eval(expression)) 
    except Exception as e:
        return f"Error: {e}"

# 2. Create the Agent and the Flow
llm = rt.llm.GeminiLLM("gemini-3.1-pro-preview")
MathAgent = rt.agent_node("MathAgent", tool_nodes=[calculator_tool], llm=llm)
my_flow = rt.Flow(name="Math Workflow", entry_point=MathAgent)

# 3. Create your FastAPI Application
app = FastAPI(title="Railtracks Math API")

# Define Data models for Request / Response
class MathRequest(BaseModel):
    query: str

class MathResponse(BaseModel):
    result: str

# 4. Integrate your Flow inside a standard async route
@app.post("/solve", response_model=MathResponse)
async def solve_math(request: MathRequest):
    try:
        # Since Flow returns an async awaitable properly, handle it seamlessly
        result = await my_flow.ainvoke(request.query)
        return MathResponse(result=str(result.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

```

To run this application, save it as `main.py` and run it via uvicorn:

```bash
uvicorn main:app --reload
```

You can then test your new endpoint by POSTing into `http://localhost:8000/solve`:

```json
{
  "query": "What is 15 multiplied by 44?"
}
```

## Advanced Logic

With FastAPI, you can inject dependency context inside Railtracks runs natively, which allows you to extract web request headers (like Authentication or User-Id tokens), and pass them tightly into your agent executions.

```python
from fastapi import Request

@app.post("/chat")
async def chat_with_context(request: Request, body: MathRequest):
    user_token = request.headers.get("Authorization")
    
    # Example logic using context variables in flow
    context = {"auth_token": user_token}
    
    result = await my_flow.ainvoke(body.query, context=context)
    return {"result": str(result.content)}
```

Railtracks makes standing up advanced agent systems behind powerful web frameworks truly un-opinionated. Take a look at the hands-on Jupyter notebook linked above for more comprehensive examples.
