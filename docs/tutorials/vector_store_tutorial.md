# Tutorial: Building a Vector Store Workflow

Let's walk through creating a full working embedding + vector store pipeline.


## Step 1: Initialize the Vector Store with your chosen provider and embedding function
```python
--8<-- "docs/scripts/vector_store_tutorial.py:chroma_imports"
--8<-- "docs/scripts/vector_store_tutorial.py:embedding_function"
--8<-- "docs/scripts/vector_store_tutorial.py:first_step"
```
!!! note "Choosing where your vector store is located"
    You can look at our different integrations to location options for your stores

## Step 2: Insert Your Documents

You can upsert:

- A string or list of strings

- A Chunk object or list of Chunk objects (if you want a custom ID or need to attach document data or metadata)

### Simple Insert
```python
--8<-- "docs/scripts/vector_store_tutorial.py:second_step"
```

### Insert With Metadata
```python
--8<-- "docs/scripts/vector_store_tutorial.py:second_step_metadata"
```

## Step 3: Search Your Data
```python
--8<-- "docs/scripts/vector_store_tutorial.py:third_step"
```

## Step 4: Fetch By ID
```python
--8<-- "docs/scripts/vector_store_tutorial.py:fourth_step"
```

## Step 5: Delete 

```python
--8<-- "docs/scripts/vector_store_tutorial.py:fifth_step"
```

## Examples

```python
--8<-- "docs/scripts/vector_store_tutorial.py:first_example"
```

```python
--8<-- "docs/scripts/vector_store_tutorial.py:second_example"
```

