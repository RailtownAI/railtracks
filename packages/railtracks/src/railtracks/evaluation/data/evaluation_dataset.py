import json
import random
from collections import defaultdict
from pathlib import Path
from uuid import UUID, uuid4

from ...utils.logging.create import get_rt_logger
from ...utils.point import AgentDataPoint

logger = get_rt_logger("EvaluationDataset")


class EvaluationDataset:
    """Local in-memory dataset implementation. Supports loading from and saving to JSON files.

    Args:
        path: Path to:  1) a JSON file containing a saved dataset with metadata and data points
                        2) a JSON file containing raw agent data points,
                        3) a directory containing raw agent data JSON files.
        name: Optional name for the dataset. If not provided, uses the filename.
    """

    def __init__(self, path: str, name: str | None = None):
        self._path = Path(path)
        self._name = name or self._path.stem

        self._data_points: dict[str, list[AgentDataPoint]] = defaultdict(list)
        self._identifier: UUID = uuid4()
        self._metadata: dict = {}

        if self._path.is_file() and self._path.suffix == ".json":
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "metadata" in data and "data_points" in data:
                self._load_from_dataset_json(self._path)
            else:
                self._load_from_json(self._path)
        elif self._path.is_dir():
            self._load_from_path(self._path)
        else:
            raise ValueError(
                "Provided path needs to be a .json file or a directory containing JSON files."
            )

    @property
    def identifier(self) -> UUID:
        """Get the dataset UUID."""
        return self._identifier

    @property
    def name(self) -> str:
        """Get the dataset name."""
        return self._name

    @property
    def data_points_dict(self) -> dict[str, list[AgentDataPoint]]:
        """Retrieve all data points in the dataset as a dictionary keyed by agent name."""
        return self._data_points.copy()

    @property
    def data_points_list(self) -> list[AgentDataPoint]:
        """Retrieve all data points in the dataset as a flat list."""
        return [dp for dps in self._data_points.values() for dp in dps]

    @property
    def agents(self) -> set[str]:
        """Retrieve all agent names in the dataset."""
        return set(self._data_points.keys())

    def sample(self, agent_name: str, n: int) -> list[AgentDataPoint]:
        """Randomly sample n data points for an agent from the dataset.

        Args:
            agent_name: The name of the agent whose data points are to be sampled.
            n: Number of data points to sample. If n is greater than the dataset size, returns all data points.
        """
        if agent_name not in self._data_points:
            logger.warning(f"Agent '{agent_name}' not found in dataset.")
            return []

        agent_data = self._data_points[agent_name]

        if n >= len(agent_data):
            logger.warning(
                f"Requested sample size {n} is greater than or equal to the number of available data points for agent '{agent_name}'. Returning all data points."
            )
            return agent_data.copy()

        return random.sample(agent_data, n)

    def insert(self, data_points: AgentDataPoint | list[AgentDataPoint]) -> None:
        """Add a new data point to the dataset.

        Args:
            data_point: The DataPoint instance to add.

        Raises:
            ValueError: If a data point with the same identifier already exists.

        """
        if isinstance(data_points, AgentDataPoint):
            data_points = [data_points]

        for dp in data_points:
            self._data_points[dp.agent_name].append(dp)

    def save(self, path: str | None = None, name: str | None = None) -> None:
        """Save dataset to a JSON file.

        Args:
            path: Path to the JSON file or directory. Must have a .json extension if file.
                  If None, uses the original path/directory from initialization.
            name: Name for the saved file (without extension). Only used if path is a directory
                  or None. If None, uses the dataset's name.

        Raises:
            ValueError: If the file extension is not .json.
        """
        save_name = name or self._name
        save_path = Path(path) if path else self._path

        if save_path.is_dir():
            save_path = save_path / f"{save_name}.json"
        elif save_path.suffix != ".json":
            raise ValueError("File must have .json extension")

        dataset_dict = {
            "metadata": {"identifier": str(self._identifier), "name": self._name},
            "data_points": {
                agent_name: [dp.model_dump(mode="json") for dp in dps]
                for agent_name, dps in self._data_points.items()
            },
        }

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(dataset_dict, f, indent=2, ensure_ascii=False)

    def delete(self, agent_name: str) -> None:
        """Remove an agent's datapoints from the dataset

        Args:
            agent_name: The name of the agent whose data points are to be removed.
        """
        try:
            del self._data_points[agent_name]
        except KeyError:
            logger.warning(
                f"Agent '{agent_name}' not found in dataset. No data points deleted."
            )

    def __len__(self) -> int:
        """Return the number of data points in the dataset."""
        return sum(len(dps) for dps in self._data_points.values())

    def __getitem__(self, agent_name: str) -> list[AgentDataPoint]:
        """Retrieves an agent's data points by agent name.

        Args:
            agent_name: The name of the agent whose data points are to be retrieved.

        Raises:
            KeyError: If no data point with the given UUID exists.
        """
        if agent_name not in self._data_points:
            logger.warning(f"Agent '{agent_name}' not found in dataset.")
            return []

        return self._data_points[agent_name].copy()

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
                logger.warning(f"Skipping unsupported file format: {file.name}")
                continue

    def _load_from_json(self, file_path: Path) -> None:
        """Load AgentDataPoint list from a JSON file (raw agent data)."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                try:
                    dp = AgentDataPoint.model_validate(item)
                    self._data_points[dp.agent_name].append(dp)
                except Exception as e:
                    logger.warning(
                        f"Skipping malformed data point in file {file_path.name}: {repr(e)}"
                    )

        except Exception as e:
            logger.warning(f"Skipping malformed file: {file_path.name}: {repr(e)}")

    def _load_from_dataset_json(self, file_path: Path) -> None:
        """Load a saved dataset file with metadata and data points."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if "metadata" in data:
                metadata = data["metadata"]
                if "identifier" in metadata:
                    self._identifier = UUID(metadata["identifier"])
                if "name" in metadata:
                    self._name = metadata["name"]

            for item in data.get("data_points", []):
                for point in data["data_points"][item]:
                    try:
                        dp = AgentDataPoint.model_validate(point)

                        if item != dp.agent_name:
                            raise ValueError(
                                f"Agent name mismatch in data points: key '{item}' vs agent_name '{dp.agent_name}'"
                            )

                        self._data_points[dp.agent_name].append(dp)
                    except Exception as e:
                        logger.warning(
                            f"Skipping malformed data point in file {file_path.name}: {repr(e)}"
                        )

        except Exception as e:
            logger.exception(
                f"Skipping malformed dataset file: {file_path.name}: {repr(e)}"
            )
            raise e
