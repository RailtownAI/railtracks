---

hide:
  - toc
---

<div class="rt-hero">
  <img src="assets/logo.svg" alt="Railtracks Logo" width="260">
  <h1>Build agents in pure Python</h1>
  <p>Minimal. Extensible. Designed for developers.</p>
  <div class="rt-video-container">
    <div class="rt-video-embed">
      <iframe src="https://player.vimeo.com/video/1166415069" title="Building with Railtracks" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
    </div>
  </div>
</div>

<div class="rt-cta">
  <a href="quickstart/quickstart" class="md-button md-button--primary">Quickstart</a>
  <a href="https://github.com/RailtownAI/railtracks-examples" class="md-button">Browse examples</a>
</div>

---

<div class="rt-section-center">
  <h1>Agent Observability</h1>
  <div class="rt-video-container">
    <div class="rt-video-embed">
      <iframe src="https://player.vimeo.com/video/1166415035" title="Observability with Railtracks" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
    </div>
  </div>
</div>

<div class="rt-cta">
  <a href="observability/visualization" class="md-button">Get started with Observability</a>
</div>

---

## Our Driving Principle: Flows Are Just Python

In Railtracks, agent behavior is defined directly in Python. There is **no** configuration language and **no** external graph definition. Execution order, branching, and looping are expressed using standard control flow.

Building a sequential flow is just like any the code you have written in your life. 
```python
@function_node
async def flow(user_input):
    a = await call(Agent1, user_input)
    b = await call(Agent2, a)
    c = await call(Agent3, b)
    return c
```

More complex behavior is built by extending this same pattern.

---

## What This Enables

The same flow model supports a range of agent architectures without introducing new abstractions.

<div class="grid cards">
  <a class="card" href="architectures/validation_loop">
    <h3>Validation Loops</h3>
    <p>Iterative workflows which allow you to iteratively improve output quality.</p>
  </a>
  <a class="card" href="architectures/sequential">
    <h3>Sequential Flows</h3>
    <p>Programmatically defining sequential and branching steps for an agent.</p>
  </a>
  <a class="card disabled">
    <h3>Orchestrator / Worker</h3>
    <p>A coordinating agent that delegates work to specialized agents or tools. <strong>Coming soon.</strong></p>
  </a>
</div>

<div class="rt-section-center">
  <div class="rt-video-container">
    <div class="rt-video-embed">
      <iframe src="https://player.vimeo.com/video/1166415011" title="Flows with Railtracks" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
    </div>
  </div>
</div>

<div class="rt-cta">
  <a href="architectures/overview" class="md-button">Checkout other architectures</a>
</div>

---

## Suggested Progression

Most users approach Railtracks in roughly this order:

1. Run the [**Quickstart**](quickstart/quickstart) to see a complete flow.
2. Explore one or two [**architecture examples**](architectures/overview).
3. Use the **API reference** for details.

---

## Community and Contribution

Railtracks is developed in the open.

* [GitHub repository](https://github.com/RailtownAI/railtracks)
* [Contribution guide](https://github.com/RailtownAI/railtracks?tab=contributing-ov-file)
* [Community discussions](https://github.com/RailtownAI/railtracks/discussions)
