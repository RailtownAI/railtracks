from collections import defaultdict
from uuid import UUID

from ...utils.logging.create import get_rt_logger
from ...utils.point import AgentDataPoint
from ..result import EvaluatorResult, LLMInferenceAggregateResult, LLMMetricResult
from .evaluator import Evaluator
from .metrics import LLMMetric

logger = get_rt_logger("LlmInferenceEvaluator")


class LLMInferenceEvaluator(Evaluator):
    def __init__(
        self,
    ):
        super().__init__()

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult[LLMMetric, LLMMetricResult | LLMInferenceAggregateResult]:

        agent_data_ids: set[UUID] = {adp.run_id for adp in data}
        results, metrics = self._retrieve_llm_states(data)
        aggregate_results = self._aggregate_metrics(results)

        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.identifier,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            results=[item for sublist in results.values() for item in sublist]
            + aggregate_results,
        )

    def _retrieve_llm_states(self, data: list[AgentDataPoint]):
        results: dict[LLMMetric, list[LLMMetricResult]] = defaultdict(list)
        keys: set[LLMMetric] = set()
        for datapoint in data:
            llm_metrics = datapoint.agent_internals.get("llm_metrics", {})

            for call in llm_metrics.get("calls", []):

                # Input Tokens
                metric = LLMMetric(
                    name="InputTokens",
                )
                results[metric].append(
                    LLMMetricResult(
                        result_name="InputTokens",
                        metric_id=metric.identifier,
                        agent_data_id=[datapoint.run_id],
                        value=call.get("input_tokens", 0),
                        llm_call_index=call.get("call_index", -1),
                        model_name=call.get("model_name", ""),
                        model_provider=call.get("model_provider", ""),
                    )
                )

                # Output Tokens
                metric = LLMMetric(
                    name="OutputTokens",
                )
                keys.add(metric)
                results[metric].append(
                    LLMMetricResult(
                        result_name="OutputTokens",
                        metric_id=metric.identifier,
                        agent_data_id=[datapoint.run_id],
                        value=call.get("output_tokens", 0),
                        llm_call_index=call.get("call_index", -1),
                        model_name=call.get("model_name", ""),
                        model_provider=call.get("model_provider", ""),
                    )
                )

                # Total Cost
                metric = LLMMetric(
                    name="TotalCost",
                )
                keys.add(metric)
                results[metric].append(
                    LLMMetricResult(
                        result_name="TotalCost",
                        metric_id=metric.identifier,
                        agent_data_id=[datapoint.run_id],
                        value=call.get("total_cost", 0.0),
                        llm_call_index=call.get("call_index", -1),
                        model_name=call.get("model_name", ""),
                        model_provider=call.get("model_provider", ""),
                    )
                )

                # Latency
                metric = LLMMetric(
                    name="Latency",
                )
                results[metric].append(
                    LLMMetricResult(
                        result_name="Latency",
                        metric_id=metric.identifier,
                        agent_data_id=[datapoint.run_id],
                        value=call.get("latency", 0.0),
                        llm_call_index=call.get("call_index", -1),
                        model_name=call.get("model_name", ""),
                        model_provider=call.get("model_provider", ""),
                    )
                )

        return results, list(results.keys())

    def _aggregate_metrics(
        self, results: dict[LLMMetric, list[LLMMetricResult]]
    ) -> list[LLMInferenceAggregateResult]:

        aggregates = []

        for metric in results:

            metric_results = results[metric]
            values: dict[tuple[str, str, int], list[float | int]] = defaultdict(list)
            for mr in metric_results:
                if isinstance(mr.value, (int, float)):
                    key = (mr.model_name, mr.model_provider, mr.llm_call_index)
                    values[key].append(mr.value)

            for (model_name, model_provider, llm_call_index), vals in values.items():
                aggregate_result = LLMInferenceAggregateResult(
                    metric=metric,
                    values=vals,
                    model_name=model_name,
                    model_provider=model_provider,
                    llm_call_index=llm_call_index,
                )
                aggregates.append(aggregate_result)
        return aggregates
