# To Do Tooling
A common addition to your agent is a tool for tracking and planning todos. Railtracks provides a built-in tool for this purpose that you can drop into your agent right away.

## Usage 
Adding the todo tool to your agent is super easy.

```python 
--8<-- "docs/scripts/todos.py:todos"
```

!!! Warning
    Todos are scoped to the `ToDoToolSet` instance. All tools returned from the same instance share one list. To maintain separate todo lists for different agents, create a separate `ToDoToolSet` instance for each.

You may want to add details around how to use the todos in your prompt. We provide a simple helper function to describe how to use it:

```python
--8<-- "docs/scripts/todos.py:todo_prompt"
```