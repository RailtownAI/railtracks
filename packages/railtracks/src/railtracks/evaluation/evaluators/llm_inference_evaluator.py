from .evaluator import Evaluator
from ...utils.logging.create import get_rt_logger
from ...utils.point import AgentDataPoint
from ..result import EvaluatorResult, MetricResult, AggregateNumericalResult
from .metrics import LLMMetric
from uuid import UUID
from collections import defaultdict

logger = get_rt_logger("LlmInferenceEvaluator")

class LLMInferenceEvaluator(Evaluator):
    def __init__(
            self,
    ):
        super().__init__()

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:

        agent_data_ids: set[UUID] = {adp.id for adp in data}
        results, metrics = self._retrieve_llm_states(data)
        aggregate_results = self._aggregate_metrics(results)
        
        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self._id,
            agent_data_ids=agent_data_ids,
            metrics=metrics,
            results=[item for sublist in results.values() for item in sublist] + aggregate_results,
        )

    def _retrieve_llm_states(
            self, data: list[AgentDataPoint]
    ):
        results: dict[LLMMetric, list[MetricResult]] = defaultdict(list)
        keys: list[LLMMetric] = []
        vals: list[MetricResult] = []
        for datapoint in data:
            llm_metrics = datapoint.agent_internals.get("llm_metrics", {})

            for call in llm_metrics.get("calls", []):
                
                # Input Tokens
                keys.append(LLMMetric(
                    name="InputTokens",
                    call_index=call.get("call_index", -1),
                    model_name = call.get("model_name", ""),
                    model_provider=call.get("model_provider", ""),
                ))
                vals.append(MetricResult(
                    result_name="InputTokens",
                    metric_id=keys[-1].identifier,
                    agent_data_id=[datapoint.id],
                    value=call.get("input_tokens", 0),
                ))

                # Output Tokens
                keys.append(LLMMetric(
                    name="OutputTokens",
                    call_index=call.get("call_index", -1),
                    model_name = call.get("model_name", ""),
                    model_provider=call.get("model_provider", ""),
                ))
                vals.append(MetricResult(
                    result_name="OutputTokens",
                    metric_id=keys[-1].identifier,
                    agent_data_id=[datapoint.id],
                    value=call.get("output_tokens", 0),
                ))

                # Total Cost
                keys.append(LLMMetric(
                    name="TotalCost",
                    call_index=call.get("call_index", -1),
                    model_name = call.get("model_name", ""),
                    model_provider=call.get("model_provider", ""),
                ))
                vals.append(MetricResult(
                    result_name="TotalCost",
                    metric_id=keys[-1].identifier,
                    agent_data_id=[datapoint.id],
                    value=call.get("total_cost", 0.0),
                ))

                # Latency
                keys.append(LLMMetric(
                    name="Latency",
                    call_index=call.get("call_index", -1),
                    model_name = call.get("model_name", ""),
                    model_provider=call.get("model_provider", ""),
                ))
                vals.append(MetricResult(
                    result_name="Latency",
                    metric_id=keys[-1].identifier,
                    agent_data_id=[datapoint.id],
                    value=call.get("latency", 0.0),
                ))

            for k, v in zip(keys, vals):
                results[k].append(v)
        return results, keys
    
    def _aggregate_metrics(self, results: dict[LLMMetric, list[MetricResult]]):
        
        aggregates = []

        for metric in results:
            
            metric_results = results[metric]
            values = [mr.value for mr in metric_results if isinstance(mr.value, (int, float))]

            aggregate_result = AggregateNumericalResult(
                metric=metric,
                values=values,
            )
            aggregates.append(aggregate_result)
        return aggregates
    
