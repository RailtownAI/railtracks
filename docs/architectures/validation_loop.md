# Validation Loops
Anyone who has spent time building agentic systems has likely run into the limits of one-shot LLM responses, especially as tasks grow more complex where precision is at a premium. This is where validation loops become useful.

A validation loop allows an agent to iteratively evaluate its own output, apply feedback, and try again until a desired bar is met. In this tutorial, we’ll walk through a simple example of building a validation loop in Railtracks. While the example uses an LLM to perform validation, the same pattern can be applied with fully programmatic checks such as schema validation, static analysis, code execution, or other custom logic.



<div class="colab-card">


  <div class="colab-card-content">
    <div class="colab-card-title">
      Agent Validation Loop Tutorial
    </div>

    <div class="colab-card-description">
      Run this tutorial interactively in Google Colab.
    </div>
  </div>

  <div class="colab-card-action">
    <a
      href="https://colab.research.google.com/drive/19r_cH3j6Pz74dvWaRku8TtEWAL_Y4v2R?usp=sharing"
      target="_blank"
      rel="noopener"
      class="colab-button"
    >
      Open in Colab →
    </a>
  </div>
</div>



