from __future__ import annotations

import pytest

from railtracks.retrieval.embedding import EmbeddingMetrics


def test_metrics_add_sums_tokens_and_cost():
    a = EmbeddingMetrics(input_tokens=5, total_cost=0.001, latency=0.1, model="m", vector_count=3, dimension=4)
    b = EmbeddingMetrics(input_tokens=3, total_cost=0.002, latency=0.2, model="m", vector_count=2, dimension=4)
    c = a + b
    assert c.input_tokens == 8
    assert c.total_cost == pytest.approx(0.003)
    assert c.latency == pytest.approx(0.3)
    assert c.vector_count == 5
    assert c.model == "m"
    assert c.dimension == 4


def test_metrics_add_none_fields_handled():
    a = EmbeddingMetrics(input_tokens=None, total_cost=None)
    b = EmbeddingMetrics(input_tokens=5, total_cost=0.001)
    c = a + b
    assert c.input_tokens == 5
    assert c.total_cost == pytest.approx(0.001)


def test_metrics_sum_builtin():
    metrics = [
        EmbeddingMetrics(input_tokens=3, total_cost=0.001),
        EmbeddingMetrics(input_tokens=4, total_cost=0.002),
    ]
    total = sum(metrics, EmbeddingMetrics())
    assert total.input_tokens == 7
    assert total.total_cost == pytest.approx(0.003)
