# Visualization

After running evaluations, results are automatically saved to `.railtracks/data/evaluations`. The built-in visualizer lets you explore these results locally with no sign up required.

!!! tip "Setting up the visualizer"
    See [Observability → Visualization](../observability/visualization.md) for installation and setup instructions.

## Exploring Evaluation Results

Once the visualizer is running, navigate to the **Evaluations** tab to browse your saved evaluation runs. For each evaluation, you can view **Per-evlauator** breakdown of the results. Subsequently, in each **Evaluator** view you can see aggregates and individual results for the corresponding metrics. Additionally, if the data for your agent runs is still locally available, you can click and inspect the run corresponding to the results. 

The short demo below provides an overview of the available views. 

???+ info "Example Setup"
    The agent being evaluated is a ***Stock Analysis Agent***. It has access to the following:

    - `get_new`
    - `get_stock_price`
    - `get_current_date`
    - `get_stock_history`
    - `WebSearchAgent` -> In **Railtracks** _agents_ can be passed to other agents as tools

    In the demo, we are evaluating this agent's performance on the following prompt:

    `"What is the current stock price of {company} and how has it changed over the past week? Why? First use the web to find the ticker."`
    where the `company` parameter covers the list `["Nvidia", "Apple", "Amazon", "Google", "Microsoft"]`


<div style="overflow: hidden; width: 100%; height: 120%;">
    <img src="../../assets/visualizer.gif"/>
</div>
