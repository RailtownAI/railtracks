import railtracks as rt
import asyncio
import yaml

from .evaluator import Evaluator
from ..data import DataPoint, Dataset
from .metrics import Metric

class ToolUseEvaluator(Evaluator):
    def __init__(self, 
                 trials: int = 1,
                 metric: Metric | None = None,
    ):
        super().__init__()


    def run(self, data: DataPoint | list[DataPoint] | Dataset):
        pass