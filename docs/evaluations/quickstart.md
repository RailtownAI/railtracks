# Evaluations

Evaluations in `railtracks` are a useful tool to analyze, aggregate, and finally visualize agent runs invoked previously. Sessions are automatically stored in `.railtracks/data/sessions`, so evaluations can be run at any time after invoking your agent.

## Evaluation Definition
```python
--8<-- "docs/scripts/evaluations/evals_quickstart.py:tutorial"
```

As long as you have previously run an agent using `railtracks`, the script above will then prompt you with:

```console
Multiple agents found in the data:
  0: FinanceAgent -> 5 data points
  1: Orchestrator -> 1 data points

Select agent index(es) (comma-separated), or -1 to evaluate all:
```

Upon selection, the results of the evaluation are automatically saved to your `.railtracks/data/evaluations` folder. You can subsequently use the `railtracks viz` command to look and analyze the results.