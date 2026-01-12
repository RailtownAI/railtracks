import json
import pytest
from pathlib import Path

from railtracks.utils.point import AgentDataPoint


# ================= Fixtures for Evaluation Tests =================


@pytest.fixture
def sample_data_points():
    """Create sample agent data points for testing."""
    return [
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "What is AI?"},
            agent_output="Artificial Intelligence is...",
        ),
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "What is ML?"},
            agent_output="Machine Learning is...",
        ),
        AgentDataPoint(
            agent_name="agent2",
            agent_input={"task": "summarize"},
            agent_output="Summary: ...",
        ),
    ]


@pytest.fixture
def raw_json_file(tmp_path, sample_data_points):
    """Create a raw JSON file with agent data points."""
    file_path = tmp_path / "raw_data.json"
    data = [dp.model_dump(mode="json") for dp in sample_data_points]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path


@pytest.fixture
def dataset_json_file(tmp_path, sample_data_points):
    """Create a dataset JSON file with metadata and data points."""
    file_path = tmp_path / "dataset.json"
    dataset_dict = {
        "metadata": {
            "identifier": "12345678-1234-5678-1234-567812345678",
            "name": "test_dataset",
        },
        "data_points": {
            "agent1": [sample_data_points[0].model_dump(mode="json"), sample_data_points[1].model_dump(mode="json")],
            "agent2": [sample_data_points[2].model_dump(mode="json")],
        },
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(dataset_dict, f)
    return file_path


@pytest.fixture
def json_directory(tmp_path, sample_data_points):
    """Create a directory with multiple JSON files."""
    dir_path = tmp_path / "json_dir"
    dir_path.mkdir()
    
    # Create first file with agent1 data
    file1 = dir_path / "data1.json"
    with open(file1, "w", encoding="utf-8") as f:
        json.dump([sample_data_points[0].model_dump(mode="json")], f)
    
    # Create second file with agent2 data
    file2 = dir_path / "data2.json"
    with open(file2, "w", encoding="utf-8") as f:
        json.dump([sample_data_points[2].model_dump(mode="json")], f)
    
    return dir_path
