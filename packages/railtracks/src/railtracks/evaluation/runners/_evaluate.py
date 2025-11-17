from typing import Literal, Type, TypeVar
from ...built_nodes.concrete._llm_base import LLMBase,LLMResponse

from ..data import DataPoint, Dataset
from ..evaluators import Evaluator
from ..result import EvaluationResult

_TOutput = TypeVar("_TOutput", bound=LLMResponse)

def evaluate(
        agent: Type[LLMBase[_TOutput, _TOutput, Literal[False]]],
        input_data: DataPoint | list[DataPoint] | Dataset,
        evaluators: Evaluator | list[Evaluator], 
) -> EvaluationResult | None:
    """
    Evaluate the given agent on the provided input data using the specified evaluators.

    Args:
        agent: The LLM agent class to be evaluated.
        input_data: A single DataPoint or a list of DataPoints to evaluate the agent on.
        evaluators: A single Evaluator or a list of Evaluators to assess the agent's performance.

    Returns:
        The evaluation results.
    """
    pass