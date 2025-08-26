# Sample script for snippet extraction tests
import math

# --8<-- [start: add_fn]
def add(a, b):
    return a + b
# --8<-- [end: add_fn]

# --8<-- [start: multiply_fn]
def multiply(a, b):
    return a * b
# --8<-- [end: multiply_fn]

# --8<-- [start: block_fn]
def block():
    x = 1
    y = 2
    return x + y
# --8<-- [end: block_fn]

# --8<-- [start: comment_fn]
# This is a comment
# --8<-- [start: inner]
def inner():
    pass
# --8<-- [end: inner]
# --8<-- [end: comment_fn]

