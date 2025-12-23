import railtracks as rt
import asyncio
import yaml
from collections import defaultdict
from pathlib import Path
from pydantic import BaseModel, Field
from .evaluator import Evaluator
from .metrics import Metric
from ..result import EvaluatorResult
from ...utils.point import AgentDataPoint

from ...utils.logging.create import get_rt_logger
from uuid import UUID, uuid4

logger = get_rt_logger("JudgeEvaluator")

class MetricResult(BaseModel):
    name: str # Would this need id?
    value: str | int | float

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

        self._template = self._load_yaml()
        
        self._metric_prompt: str = self._metrics_str()
        
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

        prompt_data = [self._prompt_template(dp) for dp in data]

        result = asyncio.run(self._session(prompt_data))

        metric_values = []

        for run_id, res in result:
            metric_values.append(res)
            
        self._result = EvaluatorResult(
            evaluator_name= self.name,
            agent_name=data[0].agent_name,
            evaluator_id=self._id,
            results=metric_values,
        )
        return self._result
    
    def __repr__(self) -> str:
        return (
            f"JudgeEvaluator(system_prompt={self._system_prompt}, "
            f"llm={self._llm}, "
            f"metric={self._metrics}, "
            f"reasoning={self._reasoning})"
        )

    async def _session(self, prompt: str | list[str]) -> list[tuple[str, JudgeResponseSchema]]:
        
        with rt.Session() as session:
            self._session_id = session._identifier
            tasks = [rt.call(self._judge, p) for p in prompt]
            response = await asyncio.gather(*tasks)
            output = [("run_id", res.structured) for res in response]
        
        return output

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
            system_prompt += "\n" +  self._template["metric"].format(
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
            metrics_str += repr(metric) + "\n"
        return metrics_str[:-1]  # Remove trailing newline
