# Filter Expressions

This library provides a small, composable filtering language for expressing structured metadata constraints
while searching or fetching vectors from your  vector store.

## Basic Concepts

A **filter expression** represents a condition on one or more fields of your metadata. There are two kinds of expressions:

- **Leaf expressions**: comparisons on a single field of your metadata
    
    For example you can specify you only want results such as:

    - `F["age"] >= 19`
    - `F["hair"] = "Brown"`
    
    Where `"age"` or `"hair"` are fields you've specified in your metadata. 


- **Logical expressions**: combinations of expressions using And/Or (see below for operator precedence)
    - `(F["age"] >= 19) & (F["hair"] == "Brown")`

    Where you are now filtering for both of these conditions to be true.
    

---

## Field References

Filters are built starting from a field reference, obtained via the global `F` object:

```python
--8<-- "docs/scripts/filtering.py:general_usage"
```

## Supported Value Types
Filter values must be one of:

- **str**
- **int**
- **float**
- **bool**
- **list of supported values**


Iterable inputs to is_in() / not_in() are normalized internally to lists.

Unsupported types (e.g. dicts, objects) will raise TypeError.

## Logical Composition
### And, Or, all_of, any_of
```python
--8<-- "docs/scripts/filtering.py:and_or_usage"
```


## Operator Precedence

Python operator precedence applies:

- & binds tighter than |
- Use parentheses for clarity

Example:

```python
a | b & c    # parsed as: a | (b & c)
```

## Invalid Usage

Filter expressions cannot be used as booleans and logical expressions must only contain filter expressions:

```python
a = (F["age"] > 18)
if a:   # raises TypeError
    ...

a & False   # raises TypeError
```

This prevents accidental evaluation and logic bugs.

## Immutability

All filter expressions are immutable. Combining expressions always produces new objects and never mutates existing ones.