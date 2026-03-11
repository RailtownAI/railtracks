from collections import defaultdict
from uuid import UUID

from ...utils.logging.create import get_rt_logger
from ..point import AgentDataPoint
from ..result import (
    AggregateForest,
    EvaluatorResult,
    LLMInferenceAggregateNode,
    LLMMetricResult,
)
from .evaluator import Evaluator
from .metrics import LLMMetric

logger = get_rt_logger("LlmInferenceEvaluator")


class LLMInferenceEvaluator(Evaluator):
    def __init__(
        self,
    ):
        super().__init__()

    def run(
        self, data: list[AgentDataPoint]
    ) -> EvaluatorResult[LLMMetric, LLMMetricResult, LLMInferenceAggregateNode]:
        agent_data_ids: set[UUID] = {adp.identifier for adp in data}
        forest = AggregateForest[LLMInferenceAggregateNode, LLMMetricResult]()

        results = self._retrieve_llm_states(data, forest)
        self._aggregate_metrics(results, forest)

        metrics = list(results.keys())

        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.identifier,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            metric_results=[item for sublist in results.values() for item in sublist],
            aggregate_results=forest,
        )

    def _retrieve_llm_states(
        self,
        data: list[AgentDataPoint],
        forest: AggregateForest[LLMInferenceAggregateNode, LLMMetricResult],
    ) -> dict[LLMMetric, list[LLMMetricResult]]:
        results: dict[LLMMetric, list[LLMMetricResult]] = defaultdict(list)

        for datapoint in data:
            llm_details = datapoint.llm_details

            for call in llm_details.calls:
                # Input Tokens
                metric = LLMMetric(
                    name="InputTokens",
                    min_value=0,
                )

                metric_result = LLMMetricResult(
                    result_name="InputTokens",
                    metric_id=metric.identifier,
                    agent_data_id=[datapoint.identifier],
                    value=call.input_tokens,
                    llm_call_index=call.index,
                    model_name=call.model_name,
                    model_provider=call.model_provider,
                )
                results[metric].append(metric_result)
                forest.add_node(metric_result)

                # Output Tokens
                metric = LLMMetric(
                    name="OutputTokens",
                    min_value=0,
                )

                metric_result = LLMMetricResult(
                    result_name="OutputTokens",
                    metric_id=metric.identifier,
                    agent_data_id=[datapoint.identifier],
                    value=call.output_tokens,
                    llm_call_index=call.index,
                    model_name=call.model_name,
                    model_provider=call.model_provider,
                )
                results[metric].append(metric_result)
                forest.add_node(metric_result)

                # Total Cost
                metric = LLMMetric(
                    name="TokenCost",
                    min_value=0.0,
                )

                metric_result = LLMMetricResult(
                    result_name="TokenCost",
                    metric_id=metric.identifier,
                    agent_data_id=[datapoint.identifier],
                    value=call.total_cost,
                    llm_call_index=call.index,
                    model_name=call.model_name,
                    model_provider=call.model_provider,
                )
                results[metric].append(metric_result)
                forest.add_node(metric_result)

                # Latency
                metric = LLMMetric(
                    name="Latency",
                    min_value=0.0,
                )
                metric_result = LLMMetricResult(
                    result_name="Latency",
                    metric_id=metric.identifier,
                    agent_data_id=[datapoint.identifier],
                    value=call.latency,
                    llm_call_index=call.index,
                    model_name=call.model_name,
                    model_provider=call.model_provider,
                )
                results[metric].append(metric_result)
                forest.add_node(metric_result)

        return results

    def _aggregate_metrics(
        self,
        results: dict[LLMMetric, list[LLMMetricResult]],
        forest: AggregateForest[LLMInferenceAggregateNode, LLMMetricResult],
    ) -> None:
        for metric in results:
            metric_results = results[metric]
            values: dict[tuple[str, str, int], list[LLMMetricResult]] = defaultdict(
                list
            )
            for mr in metric_results:
                if isinstance(mr.value, (int, float)):
                    key = (mr.model_name, mr.model_provider, mr.llm_call_index)
                    values[key].append(mr)

            for (model_name, model_provider, llm_call_index), vals in values.items():
                aggregate_node = LLMInferenceAggregateNode(
                    name=f"Aggregate/{metric.name}/{model_name}/{model_provider}/Call_{llm_call_index}",
                    metric=metric,
                    children=[val.identifier for val in vals],
                    model_name=model_name,
                    model_provider=model_provider,
                    llm_call_index=llm_call_index,
                    forest=forest,
                )

                forest.roots.append(aggregate_node.identifier)
                forest.add_node(aggregate_node)
