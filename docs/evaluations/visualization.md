# Visualization

After running evaluations, results are automatically saved to `.railtracks/data/evaluations`. The built-in visualizer lets you explore these results locally with no sign up required.

!!! tip "Setting up the visualizer"
    See [Observability → Visualization](../observability/agenthub/local.md) for installation and setup instructions.

## Exploring Evaluation Results

Once the visualizer is running, navigate to the **Evaluations** tab to browse your saved evaluation runs. For each evaluation, you can view **Per-evaluator** breakdown of the results. Subsequently, in each **Evaluator** view you can see aggregates and individual results for the corresponding metrics. Additionally, if the data for your agent runs is still locally available, you can click and inspect the run corresponding to the results. 

The short demo below provides an overview of the available views. 

???+ info "Example Setup"
    The agent being evaluated is a ***Stock Analysis Agent***. It has access to the following tools:

    - `get_new` -> Fetches the latest news articles related to the given ticker symbol
    - `get_stock_price` -> _Fetches the current stock price for the given ticker symbol_
    - `get_current_date` -> _Returns the current date in YYYY-MM-DD format_
    - `get_stock_history` -> _Fetches historical stock price data for the given ticker symbol and date range_
    - `web_search` -> _Performs a web search using the Tavily API and returns the results_

    In the demo, we are evaluating this agent's performance on the following prompt:

    `"What is the current stock price of {company} and how has it changed over the past week? Why?"`
    where the `company` parameter covers the list `["Nvidia", "Apple", "Amazon", "Google", "Microsoft"]`


<div class="rt-video-container">
  <video controls style="width: 100%; border-radius: 12px;">
    <source src="https://railtracksstorage.blob.core.windows.net/railtrackswebsite/videos/Evaluation.mp4" type="video/mp4">
  </video>
</div>
