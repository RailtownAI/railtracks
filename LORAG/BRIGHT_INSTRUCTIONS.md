# Using LORAG with the BRIGHT Dataset

This document provides instructions on how to use the LORAG system with the BRIGHT dataset.

## Overview

The BRIGHT dataset is a benchmark for retrieval tasks across various domains. It contains queries and documents with human-annotated relevance judgments. This implementation allows you to:

1. Prepare the BRIGHT dataset for use with LORAG
2. Test LORAG on individual examples from the dataset
3. Evaluate LORAG on multiple examples from the dataset

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Install the LORAG package:
```bash
pip install -e .
```

3. Prepare the BRIGHT dataset:
```bash
python eval/prepare_bright.py
```

This will download the BRIGHT dataset and prepare it for use with LORAG. By default, it will download the biology category and prepare examples with IDs 0, 100, and 1000, along with 20 documents for each example (including gold documents and some noise).

## Running Tests

### Testing a Single Example

To test LORAG with a single example from the BRIGHT dataset:

```bash
python eval/test_bright.py --category biology --example_id 0 --search_mode all --n_return 5 --effort 2
```

Parameters:
- `--category`: The category of the BRIGHT dataset to test (default: biology)
- `--example_id`: The ID of the example to test (default: 0)
- `--search_mode`: The search mode to use (all, raw, smart, or order) (default: all)
- `--n_return`: The number of results to return (default: 5)
- `--effort`: The effort level to use (default: 2)

### Simple Testing Without OpenAI API

If you don't have access to the OpenAI API or want to run a quick test, you can use the simple test script:

```bash
python eval/simple_bright_test.py --category biology --example_id 0 --n_return 5
```

This script uses a simple word overlap method for search instead of embeddings.

### Evaluating on Multiple Examples

To evaluate LORAG on multiple examples from the BRIGHT dataset:

```bash
python eval/evaluate_bright.py --category biology --search_mode all --n_return 10 --effort 2 --example_ids 0,1,2
```

Parameters:
- `--category`: The category of the BRIGHT dataset to evaluate (default: biology)
- `--search_mode`: The search mode to use (all, raw, smart, or order) (default: all)
- `--n_return`: The number of results to return (default: 10)
- `--effort`: The effort level to use (default: 2)
- `--example_ids`: Comma-separated list of example IDs to evaluate (default: 0,100,1000)

### Simple Evaluation Without OpenAI API

If you don't have access to the OpenAI API or want to run a quick evaluation, you can use the simple evaluation script:

```bash
python eval/evaluate_bright_simple.py --category biology --n_return 10
```

This script uses a simple word overlap method for search instead of embeddings.

## Running on the Full Dataset

To run on the full BRIGHT dataset, you can modify the `prepare_bright.py` script to download all categories and examples. However, this will require significant computational resources and time.

For large-scale evaluation, it's recommended to use a machine with more resources and adjust the batch size and other parameters accordingly.

### Modifying the Preparation Script

To prepare the full dataset or a different subset, you can modify the following parameters in `prepare_bright.py`:

```python
# Categories to download
categories = ["biology", "earth_science", "economics", ...]

# Sample indices to use
sample_indices = [0, 1, 2, ...]  # Or leave empty to use all examples

# Number of documents to include
num_docs = 20  # Increase for more comprehensive testing
```

## Evaluation Metrics

The evaluation scripts calculate the following metrics:

- **MRR (Mean Reciprocal Rank)**: The average of the reciprocal ranks of the first relevant document in the search results.
- **Recall@k**: The proportion of relevant documents that are retrieved in the top k results.

## Customizing LORAG for BRIGHT

The LORAG system can be customized for better performance on the BRIGHT dataset:

1. **Adjust Chunk Size**: Modify the chunk size and overlap parameters in `lorag.add_text()` to better match the document lengths in BRIGHT.

2. **Tune Search Parameters**: Experiment with different search modes, effort levels, and weights to find the optimal configuration.

3. **Implement Domain-Specific Search Methods**: Add new search methods tailored to the specific domains in BRIGHT (e.g., specialized methods for biology or economics).

## Troubleshooting

If you encounter issues with the OpenAI API, you can:

1. Check that your API key is valid and has sufficient credits
2. Use the simple test and evaluation scripts that don't require the API
3. Implement alternative embedding methods using local models