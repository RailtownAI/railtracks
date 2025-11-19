import railtracks as rt
import asyncio
import yaml
from pydantic import BaseModel, Field
from .evaluator import Evaluator
from ..data import DataPoint, Dataset
from .metrics import Metric


class JudgeResponseSchema(BaseModel):
    score: list[tuple[str, float | int | str]] = Field(
        ...,
        description="List of tuples containing metric name and its corresponding score.",
    )
    reasoning: str | None = None


class JudgeEvaluator(Evaluator):
    def __init__(
        self,
        system_prompt: str,
        llm: rt.llm.ModelBase,
        metric: list[Metric] | None = None,
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
        super().__init__()
        self._system_prompt = self._load_yaml().format(
            system_prompt=system_prompt,
            metric=str(metric) if metric else "No specific metric provided.",
        )
        self._llm = llm
        self._metric = metric
        self._reasoning = reasoning
        self._result: EvaluatorRun

        self._judge = rt.agent_node(
            system_message=self._system_prompt,
            llm=self._llm,
            output_schema=JudgeResponseSchema,
            tool_nodes=[],
        )

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
            f"metric={self._metric}, "
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

    def _load_yaml(self):
        with open("judge_evaluator.yaml", "r") as f:
            template = yaml.safe_load(f)

        print(template)
        return template["system_prompt"]
