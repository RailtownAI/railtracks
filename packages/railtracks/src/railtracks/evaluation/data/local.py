import json
import csv
from pathlib import Path
from typing import Literal
from .dataset import Dataset
from .point import DataPoint

from uuid import UUID

class LocalDataset(Dataset):
    """A simple in-memory dataset implementation."""

    def __init__(self, data_points: list[DataPoint] | None = None, path: str | None = None):
        super().__init__()
        self._data_points = data_points if data_points is not None else []
        self._path = path
        
        if self._path is not None:
            self._load_from_path(self._path)

    def _load_from_path(self, path: str) -> None:
        """Load dataset from a CSV or JSON file.
        
        Args:
            path: Path to the CSV or JSON file.
            
        Raises:
            ValueError: If file format is not supported or file doesn't exist.
            KeyError: If required fields are missing from the data.
        """
        file_path = Path(path)
        
        if not file_path.exists():
            raise ValueError(f"File not found: {path}")
        
        suffix = file_path.suffix.lower()
        
        if suffix == '.json':
            self._load_from_json(file_path)
        elif suffix == '.csv':
            self._load_from_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Only .json and .csv are supported.")
    
    def _load_from_json(self, file_path: Path) -> None:
        """Load dataset from a JSON file.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of data points")
        
        for item in data:
            # Handle UUID field if present
            if '_id' in item and isinstance(item['_id'], str):
                item['_id'] = UUID(item['_id'])
            
            data_point = DataPoint(**item)
            self._data_points.append(data_point)
    
    def _load_from_csv(self, file_path: Path) -> None:
        """Load dataset from a CSV file.
        
        Expected columns: agent_input, agent_output, expected_output (optional), _id (optional)
        """
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Handle optional expected_output field
                if 'expected_output' in row and row['expected_output'] == '':
                    row['expected_output'] = None
                
                # Handle UUID field if present, otherwise let Pydantic generate one
                if '_id' in row and row['_id']:
                    try:
                        row['_id'] = UUID(row['_id'])  # type: ignore
                    except (ValueError, AttributeError):
                        # If invalid UUID, let Pydantic generate a new one
                        row.pop('_id', None)
                else:
                    row.pop('_id', None)
                    
                data_point = DataPoint(**row)  # type: ignore
                self._data_points.append(data_point)

    def get_data_points(self) -> list[DataPoint]:
        """Retrieve all data points in the dataset."""
        return self._data_points

    def info(self) -> str:
        """Return a string representation of the dataset information."""
        return f"LocalDataset with {len(self._data_points)} data points."

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
        for dp in self._data_points:
            if dp._id == data_point_id:
                return dp
        raise KeyError(f"No data point found with id: {data_point_id}")

    def add_data_point(self, data_point: DataPoint) -> None:
        """Add a new data point to the dataset."""
        self._data_points.append(data_point)
    
    def save(self, name: str, folder: str, file_format: Literal["json", "csv"]) -> None:
        """Save dataset to a file.
        
        Args:
            name: Name of the file (without extension).
            folder: Directory path where the file will be saved.
            file_format: File format, either 'json' or 'csv'.
            
        Raises:
            ValueError: If file format is not supported.
        """
        file_path = Path(folder) / f"{name}.{file_format}"
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if file_format == 'json':
            self._save_to_json(file_path)
        elif file_format == 'csv':
            self._save_to_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_format}. Only 'json' and 'csv' are supported.")
    
    def _save_to_json(self, file_path: Path) -> None:
        """Save dataset to a JSON file."""
        data = [dp.model_dump() for dp in self._data_points]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_to_csv(self, file_path: Path) -> None:
        """Save dataset to a CSV file."""
        if not self._data_points:
            # Create empty CSV with headers
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['agent_input', 'agent_output', 'expected_output'])
                writer.writeheader()
            return
        
        # Get field names from the first data point
        fieldnames = list(self._data_points[0].model_dump().keys())
        
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for dp in self._data_points:
                row = dp.model_dump()
                # Convert None to empty string for CSV
                row = {k: (v if v is not None else '') for k, v in row.items()}
                writer.writerow(row)