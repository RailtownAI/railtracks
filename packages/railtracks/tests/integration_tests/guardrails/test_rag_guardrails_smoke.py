"""
RAG + Guardrails integration tests — NOT YET IMPLEMENTED.

The combination of RAG context injection and input/output guardrails has several
non-trivial interaction points that need dedicated tests. The tests below are a
proposed suite covering the most important cases. They should be implemented once
the RAG + guardrails contract is considered stable.

-------------------------------------------------------------------------------
PROPOSED TESTS
-------------------------------------------------------------------------------

1. test_rag_context_injected_before_input_guardrail
   ─────────────────────────────────────────────────
   Verify that the RAG context (the prepended UserMessage from `update_context`)
   is visible to the input guardrail when it runs. Concretely:
   - Set up a vector store that returns a known document ("SECRET KEYWORD").
   - Attach an input guardrail that BLOCKs if "SECRET KEYWORD" is present in
     any message.
   - Assert that the call is blocked, confirming RAG ran BEFORE the guardrail.
   - Contrast with a guardrail that ALLOWs when "SECRET KEYWORD" is present to
     confirm the injection shape.

2. test_rag_context_not_visible_to_output_guardrail
   ──────────────────────────────────────────────────
   The output guardrail receives the LLM's assistant message, not the injected
   context. Verify that the RAG injection does not bleed into the output event:
   - Use a vector store that injects a distinctive marker string.
   - Attach an output guardrail that inspects `event.output_message.content`.
   - Assert the marker is NOT present in the output event (it was a user message,
     not an assistant message).

3. test_input_guardrail_block_prevents_llm_call_even_with_rag
   ─────────────────────────────────────────────────────────────
   When an input guardrail BLOCKs, the LLM must never be called — even though
   RAG already ran and mutated the message history. Verify with a call counter
   on the mock LLM's `_structured` / `_chat` method that it stays at zero.

4. test_input_guardrail_transform_shapes_rag_injected_history
   ─────────────────────────────────────────────────────────────
   An input guardrail with action=TRANSFORM replaces the message history.
   Verify that if the guardrail transforms the history AFTER RAG injection:
   - The transformed history (not the RAG-injected one) is what the LLM sees.
   - The original history passed to `rt.call` is not mutated.

5. test_output_guardrail_block_after_rag_and_llm
   ──────────────────────────────────────────────
   Full pipeline: RAG injects context → LLM runs → output guardrail BLOCKs.
   Assert that `GuardrailBlockedError` is raised (or the appropriate error
   response is returned, depending on the public API contract).

6. test_output_guardrail_transform_replaces_llm_response_after_rag
   ─────────────────────────────────────────────────────────────────
   When the output guardrail returns TRANSFORM, the caller receives the
   transformed message, not the original LLM response. Verify end-to-end with
   a mocked LLM that returns one string and a transform guardrail that replaces
   it with another.

7. test_rag_with_populated_vector_store_injects_retrieved_content
   ────────────────────────────────────────────────────────────────
   Test with a real (in-memory) vector store that actually returns documents:
   - Upsert a small number of documents.
   - Issue a query whose embedding is close to one of them.
   - Assert the injected UserMessage contains the retrieved document text.
   - Combine with an input guardrail to confirm the guardrail sees the
     retrieved content.

8. test_rag_guardrails_terminal_agent
   ────────────────────────────────────
   The existing smoke test only covers `output_schema` (structured) agents.
   Repeat the core smoke scenario for a TerminalLLM agent (no output_schema)
   to ensure both code paths work.

9. test_rag_guardrails_streaming_agent
   ──────────────────────────────────────
   Cover the streaming variant (llm with stream=True). Confirm that guardrails
   run at the correct points in the streaming lifecycle and that RAG injection
   still occurs before the first LLM token is produced.

10. test_rag_ordering_relative_to_guardrail_is_deterministic
    ──────────────────────────────────────────────────────────
    When the same agent is invoked multiple times concurrently (via
    `asyncio.gather`), verify that each invocation sees its own isolated
    RAG-injected history and its own guardrail evaluation, with no cross-
    contamination between concurrent calls.

-------------------------------------------------------------------------------
IMPLEMENTATION NOTES
-------------------------------------------------------------------------------

- All tests should use a mock LLM (the `mock_llm` fixture from `conftest.py`)
  to remain deterministic and not require network access.
- For tests that need a populated vector store, an in-memory stub that accepts
  a configurable `search` return value is sufficient (no real embedding model
  needed).
- The `GuardrailBlockedError` import path and the exact public surface for
  handling blocked calls should be verified against the current API before
  implementing tests 5 and 6.
- Test 7 requires the embedding function to return stable vectors; a simple
  identity or fixed-vector function is fine for exercising the retrieval path
  without testing embedding quality.
"""
