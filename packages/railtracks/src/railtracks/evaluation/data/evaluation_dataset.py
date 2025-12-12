import json
from pathlib import Path
import random

from collections import defaultdict
from uuid import UUID, uuid4

from ...utils.point import AgentDataPoint

class EvaluationDataset:
    """Local in-memory dataset implementation. Supports loading from and saving to JSON files.

    Args:
        path: path to a JSON file to load data points from or to a folder of json files.
        auto_save: If True, automatically save the dataset to the specified path upon exiting a context manager.
    """

    def __init__(
        self, path: str, auto_save: bool = False
    ):
        self._path = Path(path)
        self._auto_save = auto_save

        self._agent_data_points: list[AgentDataPoint] = []
        self._data_points: dict[str, list[AgentDataPoint]] = defaultdict(list)
        
        if self._path.is_file() and self._path.suffix == ".json":
            self._load_from_json(Path(self._path))
        elif self._path.is_dir(): 
            self._load_from_path(self._path)
        else:
            raise ValueError("Provided path needs to be a .json file or a directory containing JSON files.")
        
        self._initate_data_points()
        
        
    @property
    def data_points(self) -> dict[str, list[AgentDataPoint]]:
        """Retrieve all data points in the dataset."""
        return self._data_points.copy()

    def sample(self, agent_name: str, n: int) -> list[AgentDataPoint]:
        """Randomly sample n data points for an agent from the dataset.

        Args:
            agent_name: The name of the agent whose data points are to be sampled.
            n: Number of data points to sample. If n is greater than the dataset size, returns all data points.
        """
        
        if n >= len(self._data_points[agent_name]):
            return self._data_points[agent_name].copy()

        return random.sample(self._data_points[agent_name], n)

    def insert(self, data_points: AgentDataPoint | list[AgentDataPoint]) -> None:
        """Add a new data point to the dataset.

        Args:
            data_point: The DataPoint instance to add.

        Raises:
            ValueError: If a data point with the same identifier already exists.

        """
        pass

    def save(self, path: str) -> None:
        """Save dataset to a JSON file.

        Args:
            path: Path to the JSON file. Must have a .json extension.
            
        Raises:
            ValueError: If the file extension is not .json.
        """
        pass

    def delete(self, agent_name: str) -> None:
        """Remove an agent's datapoints from the dataset
        
        Args:
            agent_name: The name of the agent whose data points are to be removed.
        """
        try:
            del self._data_points[agent_name]
        except KeyError:
            pass
            # TODO: add some warning here

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _initate_data_points(self) -> None:
        """Initialize the internal data points dictionary.
        Args:
           data_points: List of DataPoint instances to initialize the dataset with.

        """
        for agent_dp in self._agent_data_points:
            self._data_points[agent_dp.agent_name].append(agent_dp)

    def __len__(self) -> int:
        """Return the number of data points in the dataset."""
        return len(self._agent_data_points)

    def __getitem__(self, agent_name: str) -> list[AgentDataPoint]:
        """Retrieves an agent's data points by agent name.

        Args:
            data_point_id: The UUID of the data point to retrieve.

        Raises:
            KeyError: If no data point with the given UUID exists.
        """
        return self.data_points[agent_name]

    def _load_from_path(self, path: Path) -> None:
        """Load dataset from a JSON file.

        Args:
            path: Path to the JSON file.

        Raises:
            ValueError: If file format is not supported or file doesn't exist.
        """
        for file in path.iterdir():
            if file.suffix.lower() == ".json":
                self._load_from_json(file)
            else:
                continue
                # TODO: add some warning here

    def _load_from_json(self, file_path: Path) -> None:
        """Load dataset from a JSON file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            self._agent_data_points.extend([AgentDataPoint.model_validate(dp) for dp in data])
        except:
            # TODO: add warning about skipping
            pass