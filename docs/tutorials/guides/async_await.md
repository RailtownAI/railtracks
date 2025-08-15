# 🚀 Async/Await in Python

As a Python developer, the `async` and `await` keywords can sometimes stir up confusion. This guide will give you all the
basics you need to get started with RT's usage of `async` and `await`.

## ❓ What is `async/await`?

`async` and `await` are keywords in Python that unlock the ability to write asynchronous code.
This asynchronous code allows your program to behave like a multithreaded one — but in a single thread — by efficiently managing I/O-bound tasks.

Let's clarify what each keyword does:

* `async`: A keyword that you place before a function to indicate it is an async function.

```python
async def my_async_function():
    pass
```

* `await`: A keyword that you use to call an async function. It tells Python to pause the execution of the current function until the awaited function completes.

```python
async def my_async_function():
    await another_async_function()
```

!!! Warning
    `await` can only be used inside an `async` function.

!!! Tip
    If we have already lost you I encourage you to visit the [official documentation](https://docs.python.org/3/library/asyncio.html).

## 💡 When is it useful?

Asynchronous code shines when the tasks you are performing involve I/O operations, which is perfect for LLMs
because they are often waiting for a response from the LLM APIs.

## 🛠 Some Advanced Features

### 📌 Tasks

The `asyncio` library provides a way to run background tasks just like you would do with `concurrent.futures.ThreadPoolExecutor.submit(...)`.

```python
import asyncio

async def my_async_function():
    await asyncio.sleep(2)  # Simulate a long-running task
    return "Task completed"

async def main():
    task = asyncio.create_task(my_async_function())  # Create a background task to be completed soon
    result = await task # await the task just as you would with a normal async function
```

### 🤝 Gather

You can use `asyncio.gather(...)` to run multiple async functions concurrently and gather their results. This allows for
high level parallelism.

```python
import asyncio

async def task1():
    await asyncio.sleep(1)
    return "Task 1 completed"

async def task2():
    await asyncio.sleep(2)
    return "Task 2 completed"

async def main():
    results = await asyncio.gather(task1(), task2())
    print(results)  # Output: ['Task 1 completed', 'Task 2 completed']
```

## 🆚 Parallelism vs. Sequential Execution

!!! note "Parallelism"
    Each of the coroutines can run concurrently, only finishing when all of them are done.
    ```python
        await asyncio.gather(*coroutines)
    ```

!!! note "Sequential Execution"
    Each coroutine will run one after the other, waiting for each to finish before starting the next
    ```python
        await coroutine_1()
        await coroutine_2()
    ```

## 🏗 How RT uses `async/await`

If you are writing a tool in RT and need to call another tool, use `rt.call(...)`. This ensures the RT backend tracks the tool invocation, enabling logging and visualization.

!!! Note
    Because rt.call(...) returns a coroutine, your function must be declared as async (e.g., `async def my_function(...)`) so you can `await rt.call(...)`.

```python
import railtracks as rt
import asyncio

@rt.function_node
def split_text(text: str) -> list[str]:
    return text.split()

# since the alternate_capitalization function is a simple operation, it can be a regular function
@rt.function_node
def alternate_capitalization(text: str) -> str:
    return text.swapcase()

# Since the modify_text function calls other nodes, it must be an async function
# You can use the asyncio library to run the nodes however you want.
@rt.function_node
async def modify_text(text: str) -> str:
    # Call the split_text node sequentially.
    words = await rt.call(split_text, text)

    # Process each word parallelly using asyncio.gather
    modified_words = await asyncio.gather(*(rt.call(alternate_capitalization, word) for word in words))

    # Join the modified words back into a single string
    return ' '.join(modified_words)
```
