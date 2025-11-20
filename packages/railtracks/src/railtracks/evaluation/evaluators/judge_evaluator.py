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

class JudgeResponseSchema(BaseModel):
    score: list[tuple[str, float | int | str]] = Field(
        ...,
        description="List of tuples containing metric name and its corresponding score.",
    )
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
        
        self._id: UUID = uuid4()
        self._llm = llm
        self._reasoning: bool = reasoning
        self._metrics: list[Metric] | None = metrics.copy() if metrics is not None else None
        
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

    def __repr__(self) -> str:
        return (
            f"JudgeEvaluator(system_prompt={self._system_prompt}, "
            f"llm={self._llm}, "
            f"metric={self._metrics}, "
            f"reasoning={self._reasoning})"
        )

    async def _session(self, prompt: str | list[str]) -> list[tuple[str, JudgeResponseSchema]]:
        
        with rt.Session() as Session:
            if isinstance(prompt, list):
                tasks = [rt.call(self._judge, p) for p in prompt]
                response = await asyncio.gather(*tasks)
                output = [("run_id", res.structured) for res in response]

            else:
                response = await rt.call(self._judge, prompt)
                output = [("run_id", response.structured)]
        
        # How to get run id?
        return output

    def _prompt_template(self, data: DataPoint) -> str:
        prompt_inpt_section = f"Input: {data.input_data}\n"
        prompt_otpt_section = (
            f"Expected Output: {data.expected_output}\n" if data.expected_output else ""
        )
        return prompt_inpt_section + prompt_otpt_section

    def _generate_system_prompt(self, system_prompt_: str | None) -> str:
        
        system_prompt_template = self._load_yaml()
        system_prompt = ""

        if system_prompt_ is not None:
            system_prompt = system_prompt_
        else:
            system_prompt = system_prompt_template["system_prompt"]

        if self._metric_prompt:
            system_prompt += "\n" +  system_prompt_template["metric"].format(
                metrics=self._metric_prompt
            )
        
        if self._reasoning:
            system_prompt += "\n" + system_prompt_template["reasoning"]
        
        return system_prompt
    
    def _load_yaml(self):
        yaml_path = Path(__file__).parent / "judge_evaluator.yaml"
        with open(yaml_path, "r") as f:
            template = yaml.safe_load(f)

        return template

    def _metrics_str(self) -> str:
        if not self._metrics:
            return ""

        metrics_str = "Evaluation Metrics:\n"
        for metric in self._metrics:
            metrics_str += repr(metric) + "\n"
        return metrics_str
