# Visualization

After running evaluations, results are automatically saved to `.railtracks/data/evaluations`. Railtracks locates this directory by walking up from your current working directory, so results are always written to the same place regardless of where you run your scripts from. The [legacy visualizer](https://docs.railtracks.org/observability/agenthub/local/index.md) lets you explore these results locally with no sign up required. The [current visualizer](https://docs.railtracks.org/observability/agenthub/local_v2/index.md) doesn't show evaluations yet.

Setting up the visualizer

Start the legacy visualizer with `railtracks viz` (without `--beta`). See [Local Visualization (Legacy)](https://docs.railtracks.org/observability/agenthub/local/index.md) for installation and setup instructions.

## Exploring Evaluation Results

Once the visualizer is running, navigate to the **Evaluations** tab to browse your saved evaluation runs. For each evaluation, you can view **Per-evaluator** breakdown of the results. Subsequently, in each **Evaluator** view you can see aggregates and individual results for the corresponding metrics. Additionally, if the data for your agent runs is still locally available, you can click and inspect the run corresponding to the results.

The short demo below provides an overview of the available views.

Example Setup

The agent being evaluated is a ***Stock Analysis Agent***. It has access to the following tools:

- `get_new` -> Fetches the latest news articles related to the given ticker symbol
- `get_stock_price` -> *Fetches the current stock price for the given ticker symbol*
- `get_current_date` -> *Returns the current date in YYYY-MM-DD format*
- `get_stock_history` -> *Fetches historical stock price data for the given ticker symbol and date range*
- `web_search` -> *Performs a web search using the Tavily API and returns the results*

In the demo, we are evaluating this agent's performance on the following prompt:

`"What is the current stock price of {company} and how has it changed over the past week? Why?"` where the `company` parameter covers the list `["Nvidia", "Apple", "Amazon", "Google", "Microsoft"]`

\[

\](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/videos/Evaluation.mp4)
