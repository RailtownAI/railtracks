from __future__ import annotations

import hashlib
import math
import uuid
from typing import List

Vector = List[float]


def uuid_str() -> str:
    return str(uuid.uuid4())


def normalize_vector(v: Vector) -> Vector:
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return v
    return [x / norm for x in v]


def distance(a: Vector, b: Vector, metric: str = "cosine") -> float:
    """
    NOTE: lower distance == more similar for l2, higher similarity
    (returned as negative distance) for cosine / dot for convenience.
    """
    if metric == "l2":
        return sum((x - y) ** 2 for x, y in zip(a, b))

    if metric == "dot":
        return -sum(x * y for x, y in zip(a, b))  # negative for "smaller is better"

    if metric == "cosine":
        na, nb = normalize_vector(a), normalize_vector(b)
        return -sum(x * y for x, y in zip(na, nb))

    raise ValueError(f"Unsupported metric {metric}")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
