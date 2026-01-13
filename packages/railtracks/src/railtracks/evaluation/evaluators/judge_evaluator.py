import railtracks as rt
import asyncio
import yaml
from pathlib import Path
from pydantic import BaseModel
from .evaluator import Evaluator
from .metrics import Categorical, Metric
from ..result import MetricResult, EvaluatorResult, AggregateCategoricalResult
from ...utils.point import AgentDataPoint
from uuid import UUID
from ...utils.logging.create import get_rt_logger

logger = get_rt_logger("JudgeEvaluator")


class JudgeMetricResult(BaseModel):
    metric_name: str
    metric_value: str | float | int


class JudgeResponseSchema(BaseModel):
    metric_results: list[JudgeMetricResult] | None
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

        self._session_id: str
        self._llm = llm
        self._reasoning: bool = reasoning

        self._metrics: list[Metric] = metrics.copy()
        self._metrics_result: list[tuple[UUID, MetricResult]] = []
        self._metric_prompt: str = self._metrics_str()
        self._metrics_dict = {metric.name: metric for metric in self._metrics}
        self._template = self._load_yaml()

        self._system_prompt = self._generate_system_prompt(system_prompt)

        self._judge = rt.agent_node(
            system_message=self._system_prompt,
            llm=self._llm,
            output_schema=JudgeResponseSchema,
            tool_nodes=[],
        )
        super().__init__()

        self._result: EvaluatorResult

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:

        self.agent_name = data[0].agent_name

        prompt_data = [(dp.id, self._prompt_template(dp)) for dp in data]

        result: list[tuple[UUID, JudgeResponseSchema]] = asyncio.run(
            self._session(prompt_data)
        )

        results: list[tuple[UUID, JudgeMetricResult]] = []  # (ADP_id, JudgeMetricResult)

        for adp_id, res in result:
            if res.metric_results is not None: 
                results.extend([(adp_id, jmr) for jmr in res.metric_results])
            else:
                logger.warning(
                    f"No metric results returned for Judge Evaluator AgentDataPoint ID: {adp_id}"
                )

        for res in results:
            metric = self._metrics_dict.get(res[1].metric_name)
            if metric:
                self._metrics_result.append((res[0], MetricResult(
                    metric_name=res[1].metric_name,
                    metric_id=UUID(metric.identifier),
                    value=res[1].metric_value,
                ))) 
            else:
                logger.warning(
                    f"Received unknown metric name from Judge Evaluator: {res[1].metric_name}"
                )
        self.aggregate_results = self._aggregate_metrics()

        self._result = EvaluatorResult(
            evaluator_name=self.name,
            agent_name=self.agent_name,
            evaluator_id=self._id,
            results=self._metrics_result + self.aggregate_results,
            metrics=self._metrics,
        )
        return self._result

    def __repr__(self) -> str:
        return (
            f"JudgeEvaluator(system_prompt={self._system_prompt}, "
            f"llm={self._llm}, "
            f"metric={self._metrics}, "
            f"reasoning={self._reasoning})"
        )

    async def _session(
        self, prompt: list[tuple[UUID, str]]
    ) -> list[tuple[UUID, JudgeResponseSchema]]:

        # put this as none for now to not pollute agent_data
        with rt.Session(save_data="none") as session:

            # TODO: uncomment after https://github.com/RailtownAI/railtracks/issues/884 is resolved
            # self._session_id = session._identifier
            # tasks = [rt.call(self._judge, p[1]) for p in prompt]
            # response = await asyncio.gather(*tasks)
            # output = [(p[0], res.structured) for p, res in zip(prompt, response)]
            output = []
            for p in prompt:
                res = await rt.call(self._judge, p[1])
                output.append((p[0], res.structured))
        return output

    def _aggregate_metrics(self) -> list[AggregateCategoricalResult]:

        # self._aggregate_results = defaultdict(list)

        # for _,metric_result in self._metrics_result:
        #     self._aggregate_results[metric_result.metric_name].append(metric_result.value)
        aggregate_results = []

        for metric_name, metric  in self._metrics_dict.items():
            if type(metric) is not Categorical:
                continue
            # aggregate = CategoricalAggregate(
            #     name=f"{metric_name}_aggregate",
            #     metric=metric,
            #     labels=metric.categories,
            # )
            aggregate = AggregateCategoricalResult(
                metric=metric,
                labels=metric.categories,
            )
            aggregate_results.append(aggregate)

        return aggregate_results

    def _prompt_template(self, data: AgentDataPoint) -> str:
        return self._template["user"].format(
            agent_input=data.agent_input,
            agent_output=data.agent_output,
            agent_internals=data.agent_internals or {},
        )

    def _generate_system_prompt(self, system_prompt_: str | None) -> str:

        system_prompt = ""

        if system_prompt_ is not None:
            system_prompt = system_prompt_
        else:
            system_prompt = self._template["system_prompt"]

        if self._metric_prompt:
            system_prompt += "\n" + self._template["metric"].format(
                metrics=self._metric_prompt
            )

        if self._reasoning:
            system_prompt += self._template["reasoning"]

        return system_prompt

    def _load_yaml(self):
        yaml_path = Path(__file__).parent / "judge_evaluator.yaml"
        with open(yaml_path, "r") as f:
            template = yaml.safe_load(f)

        return template

    def _metrics_str(self) -> str:
        if not self._metrics:
            return ""

        metrics_str = ""
        for metric in self._metrics:
            metrics_str += str(metric) + "\n"
        return metrics_str[:-1]  # Remove trailing newline
