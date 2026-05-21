from __future__ import annotations

from enum import Enum


class DistanceMetric(str, Enum):
    """Distance metric used by a VectorBackend.

    All backends convert their native distance to a score where
    higher = more similar, using the following formulas:

        COSINE  score = 1 - cosine_distance        ∈ [-1, 1]
        L2      score = 1 / (1 + l2_distance)      ∈ (0, 1]
        IP      score = dot_product                 ∈ (−∞, ∞)

    Note: Chroma stores squared L2 internally (hnswlib), so ChromaBackend
    applies sqrt before the L2 formula to keep scores consistent with the
    other backends.
    """

    COSINE = "cosine"
    L2 = "l2"
    IP = "ip"
