---

hide:
  - toc
---


<div style="text-align:center; margin-top: 2rem; margin-bottom: 1.5rem;">
  <img src="assets/logo.svg" alt="Railtracks Logo" width="260">
  <h1 style="margin-bottom:0.25rem;">Build agents in pure Python</h1>
  <p style="margin-top:0; font-size:1rem;">
    Minimal. Extensible. Designed for developers.
  </p>

<a href="quickstart/quickstart" class="md-button md-button--primary">Quickstart</a> <a href="https://github.com/RailtownAI/railtracks-examples" class="md-button">Browse examples</a>

  <div style="margin-top: 1.5rem;">
    <iframe width="600" height="325" src="https://www.youtube.com/embed/0WJ_I_zWX8I" title="Welcome to Railtracks" frameborder="0" allowfullscreen></iframe>
  </div>
</div>

---

## Our Driving Principle: Flows Are Just Python

In Railtracks, agent behavior is defined directly in Python. There is **no** configuration language and **no** external graph definition. Execution order, branching, and looping are expressed using standard control flow.

Building a sequential flow is just like any the code you have written in your life. 
```python
@session
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
    <p>Iterative workflows such as generation with structured validation.</p>
  </a>



  <a class="card disabled">
    <h3>Research Agent</h3>
    <p>Sequential and branching steps for search, synthesis, and summarization. <strong>Coming soon.</strong></p>
  </a>

  <a class="card disabled">
    <h3>Orchestrator / Worker</h3>
    <p>A coordinating agent that delegates work to specialized agents or tools. <strong>Coming soon.</strong></p>
  </a>

</div>
<div style="text-align: center; margin-top: 1rem;">
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
