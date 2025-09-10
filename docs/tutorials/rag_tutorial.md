# RAG Tutorial

Ever wished your AI agent could know about your private documents, company policies, or the latest updates to your knowledge base? That's exactly what RAG (Retrieval-Augmented Generation) does!

This tutorial will get you from zero to RAG-powered agent in just a few minutes. We'll cover why RAG is a game-changer, how it works behind the scenes, and most importantly—how to build your first RAG application.

## Why Should You Care About RAG?

LLMs are incredibly smart, but they have some pretty big limitations:

- **No access to your private data** (company docs, internal policies, recent updates)
- **Knowledge cutoff dates**: They miss recent information
- **Hallucinations** when they confidently make up facts

RAG solves all of these problems by giving your AI access to real, up-to-date information from your own documents.

!!! tip "When RAG Shines"
    RAG is perfect when you need:

    - **Grounded answers** from internal docs, policies, FAQs, or knowledge bases
    - **Real-time accuracy** with frequently changing information
    - **Source traceability** to show exactly where answers come from
    - **Smart retrieval** when your knowledge base is too large for prompts

!!! warning "When RAG Might Be Overkill"
    Skip RAG if:

    - You only need general world knowledge your model already has
    - Your entire knowledge base easily fits in a single prompt
    - You're doing creative writing rather than fact-based responses

## How RAG Works

When you create a RAG node, RailTracks automatically handles these stages for you:

### RAG Pipeline Steps
=== "1. 📄 Chunk"
    Split each document into manageable text chunks using a token-aware strategy.
=== "2. 🔢 Embed"
    Convert each chunk to a vector using an embedding model.
=== "3. 💾 Store"
    Write vectors and associated text/metadata to a vector store (in-memory by default).
=== "4. 🔍 Search"
    At query time, embed the question and perform a similarity search to retrieve top-k relevant chunks.
=== "5. 🎯 Compose Prompt"
    Join retrieved snippets into a context string and pass it to an LLM for a grounded answer.

!!! note "Set It and Forget It"
    You don't need to wire these stages yourself when using the prebuilt node—they're executed during node construction and on each query automatically!

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
