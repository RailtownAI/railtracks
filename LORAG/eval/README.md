# Evaluating LORAG on the BRIGHT Dataset

This directory contains scripts for evaluating the LORAG system on the BRIGHT dataset.

## Overview

The BRIGHT dataset is a benchmark for retrieval tasks across various domains. It contains queries and documents with human-annotated relevance judgments.

## Setup

1. Install the required dependencies:
```bash
pip install -r ../requirements.txt
```

2. Prepare the BRIGHT dataset:
```bash
python prepare_bright.py
```

This will download the BRIGHT dataset and prepare it for use with LORAG. By default, it will download the biology category and prepare examples with IDs 0, 100, and 1000, along with 20 documents for each example (including gold documents and some noise).

## Running Tests

### Testing a Single Example

To test LORAG with a single example from the BRIGHT dataset:

```bash
python test_bright.py --category biology --example_id 0 --search_mode all --n_return 5 --effort 2
```

Parameters:
- `--category`: The category of the BRIGHT dataset to test (default: biology)
- `--example_id`: The ID of the example to test (default: 0)
- `--search_mode`: The search mode to use (all, raw, smart, or order) (default: all)
- `--n_return`: The number of results to return (default: 5)
- `--effort`: The effort level to use (default: 2)

### Evaluating on Multiple Examples

To evaluate LORAG on multiple examples from the BRIGHT dataset:

```bash
python evaluate_bright.py --category biology --search_mode all --n_return 10 --effort 2 --example_ids 0,100,1000
```

Parameters:
- `--category`: The category of the BRIGHT dataset to evaluate (default: biology)
- `--search_mode`: The search mode to use (all, raw, smart, or order) (default: all)
- `--n_return`: The number of results to return (default: 10)
- `--effort`: The effort level to use (default: 2)
- `--example_ids`: Comma-separated list of example IDs to evaluate (default: 0,100,1000)

## Evaluation Metrics

The evaluation script calculates the following metrics:

- **MRR (Mean Reciprocal Rank)**: The average of the reciprocal ranks of the first relevant document in the search results.
- **Recall@k**: The proportion of relevant documents that are retrieved in the top k results.

## Running on the Full Dataset

To run on the full BRIGHT dataset, you can modify the `prepare_bright.py` script to download all categories and examples. However, this will require significant computational resources and time.

For large-scale evaluation, it's recommended to use a machine with more resources and adjust the batch size and other parameters accordingly.