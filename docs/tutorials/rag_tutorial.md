# RAG Tutorial

This tutorial will get you from zero to RAG-powered agent in just a few minutes. We'll cover how Railtracks can help you build the perfect RAG Agent for your needs.

!!! tip "Don't know what RAG is or why you might want to use it? Check out our brief explainer [here](../background/RAG.md)"


When you create a RAG node, Railtracks automatically take care of chunking, embedding, and searching for you making it easy to use. All you need to do is provide a text file and let Railtracks take care of it for you from there. Let's look at an example of what this could look like.

##  Quickstart: Prebuilt RAG Node

This is the easiest way to add RAG to your app. Let's build a simple knowledge base in under 10 lines of code:

```python
--8<-- "docs/scripts/rag_examples.py:simple_rag_example"
```

!!! example "Example Output"
    Your RAG node can now answer questions based on your documents:

    Query: `"Who is Steve?"`

    Response: `"In our company, Steve is the lead engineer and ..."`

---

!!! success "Next Steps"
    Ready to build with RAG


    - [RAG Reference Documentation](../tools_mcp/RAG.md) to learn how to build RAG applications in RT.
    - [Tools Documentation](../tools_mcp/tools/tools.md) for integrating any type of tool.
