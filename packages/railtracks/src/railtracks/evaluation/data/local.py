import json
from pathlib import Path
import random

from .dataset import Dataset
from .point import DataPoint

from uuid import UUID


class LocalDataset(Dataset):
    """Local in-memory dataset implementation. Supports loading from and saving to JSON files.

    Args:
        data_points: Optional initial list of DataPoint instances.
        path: Optional path to a JSON file to load data points from.
        auto_save: If True, automatically save the dataset to the specified path upon exiting a context manager.
    """

    def __init__(
        self, data_points: list[DataPoint] | None = None, path: str | None = None, auto_save: bool = False
    ):
        super().__init__()

        self._data_points: dict[UUID, DataPoint] = {}
        if data_points is not None:
            self._initate_data_points(data_points)

        self._path = path
        self._auto_save = auto_save

        if self._path is not None:
            self._load_from_path(self._path)

    @property
    def data_points(self) -> list[DataPoint]:
        """Retrieve all data points in the dataset."""
        return list(self._data_points.values())

    def sample(self, n: int) -> list[DataPoint]:
        """Randomly sample n data points from the dataset.

        Args:
            n: Number of data points to sample. If n is greater than the dataset size, returns all data points.
        """
        if n >= len(self._data_points):
            return self.data_points.copy()

        return random.sample(self.data_points, n)

    def insert(self, data_points: DataPoint | list[DataPoint]) -> None:
        """Add a new data point to the dataset.

        Args:
            data_point: The DataPoint instance to add.

        Raises:
            ValueError: If a data point with the same identifier already exists.

        """
        if isinstance(data_points, list):
            for data_point in data_points:
                self.insert(data_point)
            return
        
        if isinstance(data_points, DataPoint):
            if data_points.identifier in self._data_points:
                raise ValueError(
                    f"Data point with identifier {data_points.identifier} already exists."
                )

            self._data_points[data_points.identifier] = data_points

    def save(self, path: str) -> None:
        """Save dataset to a JSON file.

        Args:
            path: Path to the JSON file. Must have a .json extension.
            
        Raises:
            ValueError: If the file extension is not .json.
        """
        file_path = Path(path)
        
        if file_path.suffix.lower() != ".json":
            raise ValueError(f"File must have .json extension, got: {file_path.suffix}")
        
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = [dp.model_dump(mode='json') for dp in self._data_points.values()]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def delete(self, data_point: DataPoint | UUID) -> None:
        """Remove a data point from the dataset.

        Args:
            data_point: The DataPoint instance or its UUID to remove.
        """
        data_point_id = data_point.identifier if isinstance(data_point, DataPoint) else data_point
        del self._data_points[data_point_id]

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._auto_save and self._path is not None:
            self.save(self._path)
        return False

    def _initate_data_points(self, data_points: list[DataPoint]) -> None:
        """Initialize the internal data points dictionary.
        Args:
           data_points: List of DataPoint instances to initialize the dataset with.

        """
        self._data_points = {}
        for data_point in data_points:
            self._data_points[data_point.identifier] = data_point

    def __len__(self) -> int:
        """Return the number of data points in the dataset."""
        return len(self._data_points)

    def __getitem__(self, data_point_id: UUID) -> DataPoint:
        """Retrieve a data point by its UUID.

        Args:
            data_point_id: The UUID of the data point to retrieve.

        Raises:
            KeyError: If no data point with the given UUID exists.
        """
        if data_point_id not in self._data_points:
            raise KeyError(f"No data point found with id: {data_point_id}")
        return self._data_points[data_point_id]

    def _load_from_path(self, path: str) -> None:
        """Load dataset from a JSON file.

        Args:
            path: Path to the JSON file.

        Raises:
            ValueError: If file format is not supported or file doesn't exist.
        """
        file_path = Path(path)

        if not file_path.exists():
            raise ValueError(f"File not found: {path}")

        if file_path.suffix.lower() != ".json":
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. Only .json is supported."
            )

        self._load_from_json(file_path)

    def _load_from_json(self, file_path: Path) -> None:
        """Load dataset from a JSON file."""
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of data points")

        for item in data:
            if "identifier" in item and isinstance(item["identifier"], str):
                item["identifier"] = UUID(item["identifier"])
            else:
                item["identifier"] = UUID() # need to create one if missing
            data_point = DataPoint(**item)
            self.insert(data_point)
