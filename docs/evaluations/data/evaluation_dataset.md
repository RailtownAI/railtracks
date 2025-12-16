More often than not, evaluations involve dealing with multiple datapoints. We wanted to make dealing with the data layer easier for developers building agents therefore we offer two ways of making a dataset to be used with evaluations:

1) By extracting past agent runs as a dataset located in a folder
2) Saving/Loading/Modifying a dataset.


## Extracting Previous Agent Runs
 **Railtracks** offers human readable tracking of your agent builds [Agent Datapoints](./agent_data.md). In this section we will show how you can utilize these previously saved runs to construct a dataset to be used for evaluations.

Let's assume we have run the agent in [Agent Datapoints](./agent_data.md) with a few different inputs. We should have a few resultant json files stored in our `.railtracks/data/agent_data` folder.

From here, we can construct a dataset from the combination of these runs with the following few lines of code:
```python
--8<-- "docs/scripts/evaluations/evaluation_dataset.py:construct"
```
The `path` parameter is multifunctional:
 
1) If the provided argument is a _directory_, it'll read and load all of the `json` files conforming to the `AgentDataPoint` class within that directory as a dataset

2) If the provided argument is a single a `json` file, you have two options:
    **i)** It's the `json` file of a single `AgentDataPoint` which will consequently be loaded as a dataset, or
    **ii)** It's the `json` file of a previously saved `EvaluationDataset` which will then be loaded.

From here on, there are many ways of interacting with the dataset:

- `dataset.agents` will list out the agents in this dataset
- `dataset.data_points` will return all of the `AgentDataPoint` as a list
- `dataset.sample(agent_name: str, n: int)` will sample `n` points from `agent_name`'s datapoints
- `dataset.insert` will insert a single or a list of `AgentDataPoint`s into the dataset
- `dataset.save` will save the dataset at the same path or a new given one as a `json` file.
- `dataset.delete(agent_name)` allows you to remove an agent's data from the dataset

We recommend playing around with this class as using previous agent runs as a dataset will prove to be incredibly useful when you are building your evaluation pipelines