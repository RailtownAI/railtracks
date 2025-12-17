# Filter Expressions

This library provides a small, composable filtering language for expressing structured metadata constraints.

The filtering system is designed to be:

- Explicit and type-safe
- Backend-agnostic
- Easy to compose and reason about
- Resistant to accidental misuse in boolean contexts

---

## Basic Concepts

A **filter expression** represents a condition on one or more fields. There are two kinds of expressions:

- **Leaf expressions**: comparisons on a single field
- **Logical expressions**: combinations of expressions using AND / OR

All filter expressions are immutable.

---

## Field References

Filters are built starting from a field reference, obtained via the global `F` object:

```python
from railtracks.vector_stores.filter import F

F["age"]
F["metadata.color"]

A field reference by itself does nothing until combined with a comparison operator.

#Comparison Operators
F["age"] == 18
F["status"] != "inactive"

#Ordering Comparisons
F["score"] > 0.8
F["score"] >= 0.5
F["rank"] < 10
F["rank"] <= 3

#Membership
F["category"].in_(["a", "b", "c"])
F["category"].not_in(["x", "y"])
```

## Supported Value Types
Filter values must be one of:

- str
- int
- float
- bool
- Enum (normalized to its .value)
- list of supported values

Examples:

```python
from enum import Enum

class Color(Enum):
    RED = "red"
    BLUE = "blue"

F["color"] == Color.RED
F["color"].in_([Color.RED, Color.BLUE])
```

Iterable inputs to in_() / not_in() are normalized internally to lists.

Unsupported types (e.g. dicts, objects) will raise TypeError.

## Logical Composition
### AND
```python
(F["age"] >= 18) & (F["country"] == "CA")
```

### OR
```python
(F["status"] == "active") | (F["priority"] > 5)
```

## Multiple Expressions

Logical expressions automatically flatten:

```python
a = F["a"] == 1
b = F["b"] == 2
c = F["c"] == 3

(a & b) & c        # equivalent to AND(a, b, c)
(a | b) | c        # equivalent to OR(a, b, c)
```


## Iterable Helpers
### all_of

Combine an iterable of expressions with AND:

```python
from railtracks.vector_stores.filter import all_of

all_of([a, b, c])
```

- Empty iterable → error
- Single element → returned as-is
- Multiple elements → AND expression

### any_of

Combine an iterable of expressions with OR:

```python
from railtracks.vector_stores.filter import any_of

any_of([a, b, c])
```

Behavior mirrors all_of, using OR instead of AND.

## Operator Precedence

Python operator precedence applies:

- & binds tighter than |
- Use parentheses for clarity

Example:

```python
a | b & c    # parsed as: a | (b & c)
```

## Invalid Usage
Boolean Contexts Are Forbidden

Filter expressions cannot be used as booleans:

```python
if F["age"] > 18:   # ❌ raises TypeError
    ...
```

This prevents accidental evaluation and logic bugs.

## Invalid Logical Children

Logical expressions must only contain filter expressions. Mixing in non-expressions is not allowed:

```python
a = F["age"] > 18
a & False   # ❌ invalid
```

## Immutability

All filter expressions are immutable. Combining expressions always produces new objects and never mutates existing ones.

## Summary

- Use F["field"] to reference fields
- Use comparison operators or explicit methods to build leaf filters
- Combine filters with &, |, and_, or_, all_of, and any_of
- Values are validated and normalized at construction time
- Expressions are safe, composable, and backend-independent