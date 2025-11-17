from abc import ABC, abstractmethod
from ..data import DataPoint, Dataset

class Evaluator(ABC):
    def __init__(self):
        self.metrics = []
        self.results = []
        self.trials = []
        pass

    @abstractmethod
    def run(self, data: DataPoint | list[DataPoint] | Dataset):
        pass
