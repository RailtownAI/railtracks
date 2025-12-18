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


- **Logical expressions**: combinations of expressions using And/Or
    - `(F["age"] >= 19) & (F["hair"] == "Brown")`

    Where you are now filtering for both of these conditions to be true.
    

---

## Field References

Filters are built starting from a field reference, obtained via the global `F` object:

```python
from railtracks.vector_stores.filter import F

F["age"]
F["color"]

# A field reference by itself does nothing until combined with a comparison operator.

#Comparison Operators
F["age"] == 18
F["status"] != "inactive"

#Ordering Comparisons
F["score"] > 0.8
F["score"] >= 0.5
F["rank"] < 10
F["rank"] <= 3

#Membership
F["category"].is_in(["a", "b", "c"])
F["category"].not_in(["x", "y"])
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

# Using and to create filter
filter1 = (F["age"] >= 18) & (F["country"] == "CA")

# Equivalently you can write
all_of([a, b, c])

#Using or to create filter
filter2 = (F["status"] == "active") | (F["priority"] > 5)

# Equivalently you can write
any_of([a, b, c])
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