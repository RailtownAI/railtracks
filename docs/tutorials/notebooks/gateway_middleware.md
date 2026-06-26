## Middleware & Context Injection

Learn how to wrap nodes and LLM calls with the two unified middleware primitives —
`Wrapper` (execution control) and `Gateway` (one-directional data transforms) —
compose them with `MiddlewareSet`, and control context injection at every scope.

Topics covered:

- Authoring a `Wrapper` (`@rt.wrapper`) for retries, fallback, and tracing
- Authoring `Gateway`s (`@rt.gateway`) and placing them in `gateway_entry` /
  `gateway_exit` for sanitisation, prompt rewriting, logging, and guardrails
- Composing reusable bands with `rt.MiddlewareSet`
- Attaching `middleware` (node boundary) vs `model_middleware` (raw model call)
- Filling `{placeholder}` templates from `rt.context` at runtime
- Disabling context injection at the global, Flow, node, and message levels

<div class="colab-card">
  <div class="colab-card-content">
    <div class="colab-card-title">
      Gateway Middleware &amp; Context Injection
    </div>
    <div class="colab-card-description">
      Run this tutorial interactively — open the notebook in <code>my_notebook/gateway_and_context_injection.ipynb</code>.
    </div>
  </div>
</div>
