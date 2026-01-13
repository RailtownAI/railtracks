Metrics are the results you would like to get out of performing evaluations on your agents. They are a parameter that can be provided to some evaluators (ie Judge) while some other evaluators only have a set of acceptable metrics (ie ToolUseEvaluator). 

In the following sections we'll go over how to use both within their respective contexts. Alternatively you can also come up with your evaluators and their metrics or customize the current ones available to fit your needs.

The main dividing factor between metrics is in the scoring capabilities; some results are based on categories (ie labels) and some are numerical values. These concepts also play a role in how different evaluators also report results.

In **Railtracks** we implement these abstractions through the following two classes that can be extended to a wide range of usecases:

- [`CategoricalMetric`](./categorical.md)
- [`NumericalMetric`](./numerical.md)