# RAG Tutorial

This tutorial will take you from zero to a RAG-powered agent in just a few minutes. We'll cover how Railtracks can help you build the perfect RAG agent for your needs.

!!! tip "New to RAG?"
    Not sure what RAG is or why you might want to use it? Check out our brief explainer [here](../background/RAG.md).

!!! warning "Vector Stores"
    To use RAG in Railtracks, you’ll need to understand how our vector stores work. You can read about them [here](../vector_stores/vector_store_info.md).

You have two options when connecting your agent to RAG. Let's start with the best, most “agentic” method.

## 1. Vector Query as a Tool

The recommended approach is to give your agent access to a tool that it can use to collect whatever information it needs. All you need to do is set up your vector store, and you’re good to go.

```python
--8<-- "docs/scripts/rag_examples.py:rag_as_tool"
```

## 2. Using a Pre-Configured RAG Node

You can also use our pre-configured RAG node that automatically collects context for the incoming question and places it in the system message. We are working diligently to expose more configurability for this functionality.

```python
--8<-- "docs/scripts/rag_examples.py:simple_rag_example"
```

!!! success "Next Steps"
    ```
    - Check out the [RAG Reference Documentation](../tools_mcp/RAG.md) to learn how to build RAG applications in Railtracks.
    - Explore the [Tools Documentation](../tools_mcp/tools/tools.md) for integrating any type of tool.
    ```
