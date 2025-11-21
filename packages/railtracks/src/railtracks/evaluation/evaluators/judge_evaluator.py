import railtracks as rt
import asyncio
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from .evaluator import Evaluator
from ..data import DataPoint, Dataset
from .metrics import Metric
from ..result import EvaluatorResult 
from uuid import UUID, uuid4

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
        system_prompt: str | None = None,
        metrics: list[Metric] | None = None,
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
        
        self._evaluator_id: UUID = uuid4()
        self._session_id: str
        self._llm = llm
        self._reasoning: bool = reasoning
        self._metrics: list[Metric] | None = metrics.copy() if metrics is not None else None
        
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



    def run(self, data: DataPoint | list[DataPoint] | Dataset):
        prompt_data = []
        if isinstance(data, DataPoint):
            prompt_data.append(self._prompt_template(data))
        elif isinstance(data, list):
            prompt_data.extend([self._prompt_template(dp) for dp in data])
        elif isinstance(data, Dataset):
            raise NotImplementedError("Dataset evaluation not implemented yet.")

        result = asyncio.run(self._session(prompt_data))

        metric_values = []
        agent_run_ids = []

        for run_id, res in result:
            metric_values.append(res)
            agent_run_ids.append(run_id)
            
        self._result = EvaluatorResult(
            name=self.name,
            evaluator_id=self._evaluator_id,
            config_hash=self.config_hash,
            results=metric_values,
            agent_run_ids=agent_run_ids,
        )

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

    def _prompt_template(self, data: DataPoint) -> str:
        return self._template["user"].format(
            agent_input=data.agent_input,
            agent_output=data.agent_output,
            expected_output=data.expected_output if data.expected_output else "N/A",
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
