"""Tree-based hierarchical aggregate structure for evaluation results.

This module provides a tree-based design for organizing aggregate results,
where parent nodes represent cross-run aggregates computed from child nodes.

Tree Structure:
- Leaf nodes: MetricResult instances (individual measurements)
- Internal nodes: AggregateTreeNode instances (computed statistics from children)
- Children can be either MetricResults (leaves) or other AggregateTreeNodes (subtrees)
"""

from __future__ import annotations

from collections import Counter
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from ..evaluators.metrics import Categorical, Numerical
from .metric_results import LLMMetricResult, MetricResult, ToolMetricResult

TMetric = TypeVar("TMetric", Numerical, Categorical)
TMetricResult = TypeVar("TMetricResult", bound=MetricResult)
TAggregateNode = TypeVar("TAggregateNode", bound="AggregateTreeNode")


class AggregateForest(BaseModel, Generic[TAggregateNode, TMetricResult]):
    """Represents a forest of aggregate trees for an evaluation."""

    roots: list[UUID] = Field(default_factory=list)
    nodes: dict[UUID, TAggregateNode | TMetricResult] = Field(default_factory=dict)

    def add_node(self, node: TAggregateNode | TMetricResult) -> None:
        """Add a node to the forest and update parent-child relationships."""
        self.nodes[node.identifier] = node

    def get(self, node_id: UUID) -> TAggregateNode | TMetricResult:
        """Retrieve a node by its identifier."""
        node = self.nodes.get(node_id)
        if node is None:
            raise KeyError(f"Node with id {node_id} not found in forest")
        return node


class AggregateTreeNode(BaseModel, Generic[TMetric]):
    """Base tree node for hierarchical aggregates.

    Represents a node in the aggregate tree that can have children.
    Children can be either:
    - MetricResult instances (leaf nodes with individual measurements)
    - Other AggregateTreeNode instances (subtrees)

    Parent nodes automatically compute aggregate statistics from all descendant values.
    """

    identifier: UUID = Field(default_factory=uuid4)
    type: str
    name: str
    metric: TMetric
    children: list[UUID] = Field(default_factory=list)

    forest: AggregateForest[AggregateTreeNode, MetricResult] = Field(exclude=True)

    @property
    def is_leaf(self) -> bool:
        """Returns True if this is a leaf node (no children)."""
        return len(self.children) == 0

    @property
    def is_parent(self) -> bool:
        """Returns True if this is a parent node (has children)."""
        return len(self.children) > 0


class NumericalAggregateNode(AggregateTreeNode[Numerical]):
    """Tree node for numerical aggregates.

    Children can be either:
    - MetricResult instances (leaf nodes with individual measurements)
    - Other NumericalAggregateNode instances (subtrees)

    Parent nodes automatically compute statistics (mean, std, etc.) from all descendant values.
    """

    type: str = "NumericalAggregate"
    forest: AggregateForest[NumericalAggregateNode, MetricResult] = Field(exclude=True)  # type: ignore[assignment]

    @computed_field
    @property
    def values(self) -> list[float | int]:
        """Recursively collect all values from this node and descendants."""
        return self._get_all_values()

    @computed_field
    @property
    def mean(self) -> float | None:
        """Mean of all values (including from children)."""
        all_values = self._get_all_values()
        return sum(all_values) / len(all_values) if all_values else None

    @computed_field
    @property
    def minimum(self) -> float | int | None:
        """Minimum of all values (including from children)."""
        all_values = self._get_all_values()
        return min(all_values) if all_values else None

    @computed_field
    @property
    def maximum(self) -> float | int | None:
        """Maximum of all values (including from children)."""
        all_values = self._get_all_values()
        return max(all_values) if all_values else None

    @computed_field
    @property
    def median(self) -> float | None:
        """Median of all values (including from children)."""
        all_values = self._get_all_values()
        if not all_values:
            return None

        sorted_values = sorted(all_values)
        n = len(sorted_values)
        if n % 2 == 0:
            return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
        else:
            return sorted_values[n // 2]

    @computed_field
    @property
    def std(self) -> float | None:
        """Standard deviation of all values (including from children)."""
        all_values = self._get_all_values()
        if not all_values or self.mean is None:
            return None

        variance = sum((x - self.mean) ** 2 for x in all_values) / len(all_values)
        return variance**0.5

    @computed_field
    @property
    def mode(self) -> float | int | None:
        """Mode of all values (including from children)."""
        all_values = self._get_all_values()
        if not all_values:
            return None

        value_counts = Counter(all_values)
        return value_counts.most_common(1)[0][0]

    def _get_all_values(self) -> list[float | int]:
        """Recursively collect all values from this node and descendants."""
        all_values = []

        for child_id in self.children:
            child = self.forest.get(child_id)
            if isinstance(child, MetricResult):
                # Leaf node, extract value from MetricResult
                if isinstance(child.value, (int, float)):
                    all_values.append(child.value)
            else:
                all_values.extend(
                    child.values
                )  # Recursively get values from child AggregateTreeNode

        return all_values


class CategoricalAggregateNode(AggregateTreeNode[Categorical]):
    """Tree node for categorical aggregates.

    Children can be either:
    - MetricResult instances (leaf nodes with individual categorical labels)
    - Other CategoricalAggregateNode instances (subtrees)

    Parent nodes automatically compute category counts from all descendant labels.
    """

    type: str = "CategoricalAggregate"
    forest: AggregateForest[CategoricalAggregateNode, MetricResult] = Field(  # type: ignore[assignment]
        exclude=True
    )

    @computed_field
    @property
    def categories(self) -> list[str]:
        """Unique categories from all labels (including from children)."""
        return list(self.metric.categories)

    @computed_field
    @property
    def counts(self) -> Counter:
        """Category counts from all labels (including from children)."""
        all_labels = self._get_all_labels()
        counts = dict.fromkeys(self.categories, 0)
        for label in all_labels:
            if label in counts:
                counts[label] += 1
        return Counter(counts)

    @computed_field
    @property
    def most_common_label(self) -> str | None:
        """Most common label across all data (including from children)."""
        return self.counts.most_common(1)[0][0]

    @computed_field
    @property
    def least_common_label(self) -> str | None:
        """Least common label across all data (including from children)."""
        return self.counts.most_common()[-1][0]

    def _get_all_labels(self) -> list[str]:
        """Recursively collect all labels from this node and descendants."""
        all_labels = []

        # Recursively collect from children
        for child_id in self.children:
            child = self.forest.get(child_id)
            if isinstance(child, MetricResult):
                if isinstance(child.value, str):
                    all_labels.append(child.value)
            else:
                all_labels.extend(child._get_all_labels())

        return all_labels

    def model_post_init(self, __context) -> None:
        """Validate that all labels are valid categories."""
        all_labels = self._get_all_labels()
        for label in all_labels:
            if label not in self.metric.categories:
                raise ValueError(f"Unknown label '{label}' not in metric categories")


class ToolAggregateNode(NumericalAggregateNode):
    """Tree node for tool-specific numerical aggregates.

    Children can be either:
    - ToolMetricResult instances (leaf nodes with individual tool measurements)
    - Other ToolAggregateNode instances (subtrees for organizing by run/environment)

    Organizes tool metrics by run, with parent node representing cross-run statistics.
    """

    type: str = "ToolAggregate"
    tool_name: str
    forest: AggregateForest[ToolAggregateNode, ToolMetricResult] = Field(exclude=True)  # type: ignore[assignment]


class LLMInferenceAggregateNode(NumericalAggregateNode):
    """Tree node for LLM inference numerical aggregates.

    Children can be either:
    - LLMMetricResult instances (leaf nodes with individual LLM measurements)
    - Other LLMInferenceAggregateNode instances (subtrees for organizing by run/model)

    Organizes LLM metrics by run, with parent node representing cross-run statistics.
    """

    type: str = "LLMInferenceAggregate"
    llm_call_index: int
    model_name: str
    model_provider: str
    forest: AggregateForest[LLMInferenceAggregateNode, LLMMetricResult] = Field(  # type: ignore[assignment]
        exclude=True
    )
