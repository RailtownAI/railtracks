# Evaluations

Evaluations in `railtracks` are a useful tool to analyze, aggregate, and finally visualize agent runs invoked previously. Therefore, to run evaluations you need previously run agent runs which are automatically stored in `.railtracks/data/sessions` folder.

# Evaluation Definition
```python
--8<-- "docs/scripts/evaluations/quickstart.py:tutorial"
```

As long as you have previously run an agent using `railtracks`, the above script above will then prompt you with:

```console
Multiple agents found in the data:
  0: FinanceAgent -> 5 data points
  1: Orchestrator -> 1 data points

Select agent index(es) (comma-separated), or -1 to evaluate all:
```

Upon selection, the results of the evaluation are automatically saved to your `.railtracks/data/evaluations` folder. You can subsequently use the `railtracks viz` command to look and analyze the results.