#!/usr/bin/env python3

import railtracks as rt


def example_function(x: int, y: int) -> float:
    return x + y


function = rt.function_node(example_function)

if __name__ == "__main__":
    result = rt.call_sync(function, 5, 10)
    print(f"Result of calling function: {result}")
