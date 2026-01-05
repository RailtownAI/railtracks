import railtracks as rt
import asyncio
import yaml
from collections import defaultdict
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from .evaluator import Evaluator
from .metrics import Metric
from ..result import MetricResult, EvaluatorResult
from ...utils.point import AgentDataPoint

from ...utils.logging.create import get_rt_logger

logger = get_rt_logger("JudgeEvaluator")

class JudgeResponseSchema(BaseModel):
    metric_results: list[MetricResult] | None
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
        self._metrics_result: dict[str, list[Metric]] = defaultdict(list)
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

        prompt_data = [self._prompt_template(dp) for dp in data]

        result: list[tuple[str, JudgeResponseSchema]] = asyncio.run(
            self._session(prompt_data)
        )

        metric_values: list[MetricResult] = []

        for run_id, res in result:
            if res.metric_results is not None:
                metric_values.extend(res.metric_results)
            else:
                logger.warning(
                    f"No metric results returned for Judge Evaluator run_id: {run_id}"
                )

        # self._aggregate_metrics(metric_values)
        
        self._result = EvaluatorResult(
            evaluator_name=self.name,
            agent_name=self.agent_name,
            evaluator_id=self._id,
            results=metric_values,
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
        self, prompt: str | list[str]
    ) -> list[tuple[str, JudgeResponseSchema]]:

        # put this as none for now to not pollute agent_data
        with rt.Session(save_data="none") as session:
            self._session_id = session._identifier
            tasks = [rt.call(self._judge, p) for p in prompt]
            response = await asyncio.gather(*tasks)
            output = [("run_id", res.structured) for res in response]

        return output

    # def _aggregate_metrics(self, metric_results: list[MetricResult]):

    #     self._aggregate_inputs = []

    #     for metric_result in metric_results:
    #         if metric_result.name in self._metrics_dict:
    #             self._aggregate_inputs.append((self._metrics_dict[metric_result.name], metric_result.value))
        

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
