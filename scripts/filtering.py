# --8<-- [start: general_usage]
from railtracks.vector_stores import F

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
# --8<-- [end: general_usage]

# --8<-- [start: and_or_usage]
from railtracks.vector_stores import all_of, any_of, F

# Using and to create filter
a = F["age"] >= 18
b = F["country"] == "CA"
c = F["status"] == "active"

filter1 = a & b & c

# Equivalently you can write
all_of([a, b, c])

#Using or to create filter
filter2 = (a | b | c)

# Equivalently you can write
any_of([a, b, c])
# --8<-- [end: and_or_usage]