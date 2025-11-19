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

    # after running the agent, how can we read the results for
    # each run and how do we aggregate them?
    def run(self, data: DataPoint | list[DataPoint] | Dataset):
        pass