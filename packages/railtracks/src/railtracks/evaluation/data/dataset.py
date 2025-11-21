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
    def get_data_points(self) -> list[DataPoint]:
        """Retrieve all data points in the dataset."""
        pass

    @abstractmethod
    def info(self) -> str:
        """Return a string representation of the dataset information."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of data points in the dataset."""
        pass

    @abstractmethod
    def __getitem__(self, data_point_id: UUID) -> DataPoint:
        """Retrieve a data point by its UUID."""
        pass

    @abstractmethod
    def add_data_point(self, data_point: DataPoint) -> None:
        """Add a new data point to the dataset."""
        pass
