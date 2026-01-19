from collections import defaultdict
import railtracks as rt
import asyncio
import yaml
from pathlib import Path
from pydantic import BaseModel
from .evaluator import Evaluator
from .metrics import Metric, Numerical, Categorical
from ..result import (
    AggregateNumericalResult,
    MetricResult,
    EvaluatorResult,
    AggregateCategoricalResult,
)
from ...utils.point import AgentDataPoint
from uuid import UUID
from ...utils.logging.create import get_rt_logger
from tqdm import tqdm

logger = get_rt_logger("JudgeEvaluator")


class JudgeResponseSchema(BaseModel):
    metric_value: str | float | int
    reasoning: str | None = None


class JudgeEvaluator(Evaluator):
    def __init__(
        self,
        llm: rt.llm.ModelBase,
        metrics: list[Metric],
        system_prompt: str | None = None,
        reasoning: bool = True,
    ):
        """
        The JudgeEvaluator with a system prompt, LLM, metric, and reasoning flag.

        Args:
            system_prompt: The system prompt template for the judge LLM.
            llm: The LLM model to be used as the judge.
            metric: An optional Metric to guide the evaluation.
            reasoning: A flag indicating whether the judge should provide reasoning for its evaluations.
        """

        self._metrics: dict[str, Metric] = {m.identifier: m for m in metrics}
        self._metrics_result: list[tuple[UUID, MetricResult]] = []
        self.results: dict[Metric, list[tuple[str, MetricResult]]] = defaultdict(list)

        # preparing the judge agent
        self._llm = llm
        self._reasoning: bool = reasoning

        self._template = self._load_yaml()
        self._session_id: str

        super().__init__()
        self._judge = rt.agent_node(
            llm=self._llm,
            output_schema=JudgeResponseSchema,
            tool_nodes=[],
        )

        self._result: EvaluatorResult

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:

        # (metric_id, adp_id, JudgeResponseSchema)
        judge_outputs: list[tuple[str, str, JudgeResponseSchema]] = asyncio.run(
            self._session(data)
        )

        for output in judge_outputs:
            metric = self._metrics[output[0]]
            self.results[metric].append(
                (
                    output[1],
                    MetricResult(
                        metric_name=metric.name,
                        metric_id=metric.identifier,
                        value=output[2].metric_value,
                    ),
                )
            )
            if self._reasoning:
                reasoning_metric = Metric(name=f"{metric.name}_reasoning")
                if output[2].reasoning is not None:
                    self.results[reasoning_metric].append(
                        (
                            output[1],
                            MetricResult(
                                metric_name=reasoning_metric.name,
                                metric_id=reasoning_metric.identifier,
                                value=output[2].reasoning,
                            ),
                        )
                    )
                else:
                    logger.warning(
                        f"No reasoning returned for Judge Evaluator Metric: {metric.name}, AgentDataPoint ID: {output[1]}"
                    )

        self.aggregate_results = self._aggregate_metrics()

        self._result = EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self._id,
            results=self._metrics_result + self.aggregate_results,
            metrics=list(self._metrics.values()),
        )
        return self._result

    def __repr__(self) -> str:
        return (
            f"JudgeEvaluator, "
            f"llm={self._llm}, "
            f"metrics={list(self._metrics.values())}, "
            f"reasoning={self._reasoning})"
        )

    async def _session(
        self, data: list[AgentDataPoint]
    ) -> list[tuple[str, str, JudgeResponseSchema]]:

        # put this as none for now to not pollute agent_data
        with rt.Session(save_data="none", logging_setting="CRITICAL") as session:

            # TODO: uncomment after https://github.com/RailtownAI/railtracks/issues/884 is resolved
            # self._session_id = session._identifier
            # tasks = [rt.call(self._judge, p[1]) for p in prompt]
            # response = await asyncio.gather(*tasks)
            # output = [(p[0], res.structured) for p, res in zip(prompt, response)]
            output = []
            for metric in self._metrics.values():
                for adp in tqdm(
                    data,
                    desc=f"LLMJudge Evaluating Agent Datapoints for metric: {metric.name}",
                ):

                    user_message = self._generate_user_prompt(adp)
                    system_message = self._generate_system_prompt(metric)

                    res = await rt.call(
                        self._judge,
                        rt.llm.MessageHistory(
                            [
                                rt.llm.SystemMessage(system_message),
                                rt.llm.UserMessage(user_message),
                            ]
                        ),
                    )
                    output.append((metric.identifier, str(adp.id), res.structured))

        return output

    def _aggregate_metrics(
        self,
    ) -> list[AggregateCategoricalResult | AggregateNumericalResult]:

        aggregates: list[AggregateCategoricalResult | AggregateNumericalResult] = []

        for metric in self.results:
            # TODO: the conditions of type checking in values and labels feels it can be better addressed
            if isinstance(metric, Numerical):
                aggregates.append(
                    AggregateNumericalResult(
                        metric=metric,
                        values=[
                            m.value
                            for _, m in self.results[metric]
                            if isinstance(m.value, (int, float))
                        ],
                    )
                )
            elif isinstance(metric, Categorical):
                aggregates.append(
                    AggregateCategoricalResult(
                        metric=metric,
                        labels=[
                            m.value
                            for _, m in self.results[metric]
                            if isinstance(m.value, str)
                        ],
                    )
                )
            elif "_reasoning" in metric.name:  # TODO: this is hacky, fix later
                continue
            else:
                logger.warning(
                    f"Supported metrics are of types Categorical or Numerical, encountered f{type(metric)}"
                )

        return aggregates

    def _generate_user_prompt(self, data: AgentDataPoint) -> str:
        return self._template["user"].format(
            agent_input=data.agent_input,
            agent_output=data.agent_output,
            agent_internals=data.agent_internals or {},
        )

    def _generate_system_prompt(self, metric: Metric) -> str:

        system_prompt: str = self._template["system_prompt"]

        system_prompt += "\n" + self._template["metric"].format(metric=str(metric))

        if self._reasoning:
            system_prompt += self._template["reasoning"]

        return system_prompt

    def _load_yaml(self):
        yaml_path = Path(__file__).parent / "judge_evaluator.yaml"
        with open(yaml_path, "r") as f:
            template = yaml.safe_load(f)

        return template
