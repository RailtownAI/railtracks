import railtracks as rt
import asyncio

from .evaluator import Evaluator
from ..data import DataPoint, Dataset

class JudgeEvaluator(Evaluator):
    def __init__(self, 
                 system_prompt: str, 
                 llm: rt.llm.ModelBase):
        super().__init__()
        self.system_prompt = system_prompt
        self._llm = llm

        self._judge = rt.agent_node(
            system_message=self.system_prompt,
            llm=self._llm,
        )

    def run(self, data: DataPoint | list[DataPoint] | Dataset):
        
        prompt_data = []
        if isinstance(data, DataPoint):
            prompt_data = self._prompt_template(data)
        if isinstance(data, Dataset):
            raise NotImplementedError("Dataset evaluation not implemented yet.")
        elif isinstance(data, list):
            raise NotImplementedError("List of DataPoints evaluation not implemented yet.")
        
        asyncio.run(self._session(prompt_data))

    async def _session(self, prompt: str | list[str]):
        if isinstance(prompt, list):
            tasks = [rt.call(self._judge, p) for p in prompt]
            responses = await asyncio.gather(*tasks)
            return [r.content for r in responses]
        else:
            response = await rt.call(self._judge, prompt)
            return response.content
        
    def _prompt_template(self, data: DataPoint) -> str:
        prompt_inpt_section = f"Input: {data.input_data}\n"
        prompt_otpt_section = f"Expected Output: {data.expected_output}\n" if data.expected_output else ""
        return prompt_inpt_section + prompt_otpt_section