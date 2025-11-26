from abc import ABC, abstractmethod
from pydantic import BaseModel
from railtracks.evaluation.data.point import DataPoint
from uuid import UUID, uuid4

class Dataset(ABC, BaseModel):
    """Abstract base class for datasets used in evaluations."""
    def __init__(self):
        super().__init__()
        self._id: UUID = uuid4()

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of data points in the dataset."""
        pass

    @abstractmethod
    def __getitem__(self, data_point_id: UUID) -> DataPoint:
        """Retrieve a data point by its UUID."""
        pass

    @abstractmethod
    def insert(self, data_points: DataPoint | list[DataPoint]) -> None:
        """Add a new data point to the dataset."""
        pass

    @abstractmethod
    def delete(self, data_point: DataPoint | UUID) -> None:
        """Remove a data point from the dataset.
        
        Args:
            data_point: The DataPoint instance or its UUID to remove.
        """
        pass
