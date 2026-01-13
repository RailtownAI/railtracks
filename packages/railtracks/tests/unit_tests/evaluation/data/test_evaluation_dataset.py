import json
import pytest
from uuid import UUID

from railtracks.evaluation.data.evaluation_dataset import EvaluationDataset
from railtracks.utils.point import AgentDataPoint


# ================= Initialization Tests =================


def test_initialization_with_various_sources(raw_json_file, dataset_json_file, json_directory):
    """Test initialization from raw JSON, dataset JSON, and directory."""
    # Raw JSON file
    dataset = EvaluationDataset(path=str(raw_json_file))
    assert dataset.name == "raw_data" and len(dataset) == 3
    assert "agent1" in dataset.agents and len(dataset["agent1"]) == 2
    
    # Dataset JSON with metadata
    dataset = EvaluationDataset(path=str(dataset_json_file))
    assert dataset.name == "test_dataset"
    assert dataset.identifier == UUID("12345678-1234-5678-1234-567812345678")
    
    # Directory with multiple files
    dataset = EvaluationDataset(path=str(json_directory))
    assert dataset.name == "json_dir" and len(dataset) == 2
    
    # Custom name
    dataset = EvaluationDataset(path=str(raw_json_file), name="custom_name")
    assert dataset.name == "custom_name"


def test_initialization_with_invalid_path(tmp_path):
    """Test initialization with an invalid path raises ValueError."""
    invalid_path = tmp_path / "nonexistent.txt"
    
    with pytest.raises(ValueError, match="Provided path needs to be a .json file or a directory"):
        EvaluationDataset(path=str(invalid_path))


def test_initialization_with_malformed_json(tmp_path):
    """Test initialization with malformed JSON file."""
    malformed_file = tmp_path / "malformed.json"
    with open(malformed_file, "w", encoding="utf-8") as f:
        f.write("{invalid json")
    
    with pytest.raises(json.JSONDecodeError):
        EvaluationDataset(path=str(malformed_file))


def test_initialization_skips_malformed_data_points(tmp_path):
    """Test that malformed data points are skipped with a warning."""
    file_path = tmp_path / "partial_data.json"
    data = [
        {
            "agent_name": "agent1",
            "agent_input": {"query": "test"},
            "agent_output": "output",
        },
        {
            "invalid": "data point without required fields"
        },
    ]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    
    dataset = EvaluationDataset(path=str(file_path))
    
    # Should only have the valid data point
    assert len(dataset) == 1
    assert "agent1" in dataset.agents


def test_initialization_skips_non_json_files(tmp_path):
    """Test that non-JSON files in a directory are skipped."""
    dir_path = tmp_path / "mixed_files"
    dir_path.mkdir()
    
    # Create a valid JSON file
    json_file = dir_path / "data.json"
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="output",
    )
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump([data_point.model_dump(mode="json")], f)
    
    # Create a non-JSON file
    txt_file = dir_path / "readme.txt"
    with open(txt_file, "w") as f:
        f.write("This is not JSON")
    
    dataset = EvaluationDataset(path=str(dir_path))
    
    # Should only load from the JSON file
    assert len(dataset) == 1


# ================= Property Tests =================


def test_dataset_properties(raw_json_file):
    """Test identifier, name, data_points_dict, data_points_list, and agents properties."""
    dataset = EvaluationDataset(path=str(raw_json_file), name="test_name")
    
    # Identifier and name
    assert isinstance(dataset.identifier, UUID)
    assert dataset.name == "test_name"
    
    # data_points_dict (shallow copy)
    data_dict = dataset.data_points_dict
    assert isinstance(data_dict, dict) and "agent1" in data_dict
    original_agents = dataset.agents.copy()
    data_dict["new_agent"] = []
    assert dataset.agents == original_agents  # Not affected
    
    # data_points_list
    data_list = dataset.data_points_list
    assert isinstance(data_list, list) and len(data_list) == 3
    assert all(isinstance(dp, AgentDataPoint) for dp in data_list)
    
    # agents property
    agents = dataset.agents
    assert isinstance(agents, set) and agents == {"agent1", "agent2"}


# ================= Sample Method Tests =================


def test_sample_method(raw_json_file):
    """Test sampling data points with various scenarios."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    # Valid sampling
    sampled = dataset.sample("agent1", n=1)
    assert len(sampled) == 1 and sampled[0].agent_name == "agent1"
    
    # n exceeds available
    sampled = dataset.sample("agent2", n=10)
    assert len(sampled) == 1  # Returns all available
    
    # Nonexistent agent
    assert dataset.sample("nonexistent_agent", n=5) == []
    
    # Returns copy (modifying doesn't affect original)
    sampled = dataset.sample("agent1", n=2)
    original_count = len(dataset["agent1"])
    sampled.clear()
    assert len(dataset["agent1"]) == original_count


# ================= Insert Method Tests =================


def test_insert_single_data_point(raw_json_file):
    """Test inserting a single data point."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    original_count = len(dataset["agent1"])
    
    new_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "new query"},
        agent_output="new output",
    )
    
    dataset.insert(new_point)
    
    assert len(dataset["agent1"]) == original_count + 1
    assert new_point in dataset["agent1"]


def test_insert_list_of_data_points(raw_json_file):
    """Test inserting a list of data points."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    original_count = len(dataset)
    
    new_points = [
        AgentDataPoint(
            agent_name="agent3",
            agent_input={"task": "translate"},
            agent_output="Translated text",
        ),
        AgentDataPoint(
            agent_name="agent3",
            agent_input={"task": "summarize"},
            agent_output="Summary text",
        ),
    ]
    
    dataset.insert(new_points)
    
    assert len(dataset) == original_count + 2
    assert "agent3" in dataset.agents
    assert len(dataset["agent3"]) == 2


def test_insert_for_new_agent(raw_json_file):
    """Test inserting data point for a new agent."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    new_point = AgentDataPoint(
        agent_name="new_agent",
        agent_input={"input": "test"},
        agent_output="output",
    )
    
    dataset.insert(new_point)
    
    assert "new_agent" in dataset.agents
    assert len(dataset["new_agent"]) == 1


# ================= Save Method Tests =================


def test_save_to_json_file(raw_json_file, tmp_path):
    """Test saving dataset to a JSON file."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    save_path = tmp_path / "saved_dataset.json"
    
    dataset.save(path=str(save_path))
    
    assert save_path.exists()
    
    # Verify the saved content
    with open(save_path, encoding="utf-8") as f:
        saved_data = json.load(f)
    
    assert "metadata" in saved_data
    assert "data_points" in saved_data
    assert saved_data["metadata"]["name"] == dataset.name
    assert str(dataset.identifier) == saved_data["metadata"]["identifier"]


def test_save_to_directory(raw_json_file, tmp_path):
    """Test saving dataset to a directory."""
    dataset = EvaluationDataset(path=str(raw_json_file), name="my_dataset")
    save_dir = tmp_path / "save_dir"
    save_dir.mkdir()
    
    dataset.save(path=str(save_dir))
    
    expected_file = save_dir / "my_dataset.json"
    assert expected_file.exists()


def test_save_with_custom_name(raw_json_file, tmp_path):
    """Test saving dataset with a custom name."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    save_dir = tmp_path / "save_dir"
    save_dir.mkdir()
    
    dataset.save(path=str(save_dir), name="custom_name")
    
    expected_file = save_dir / "custom_name.json"
    assert expected_file.exists()


def test_save_without_path_uses_original_path(raw_json_file):
    """Test saving without specifying path uses the original path."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    # Add a new data point to differentiate
    dataset.insert(AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "added"},
        agent_output="added output",
    ))
    
    dataset.save()
    
    # Reload and verify the new data point exists
    reloaded = EvaluationDataset(path=str(raw_json_file))
    assert len(reloaded) == 4


def test_save_invalid_extension_raises_error(raw_json_file, tmp_path):
    """Test that saving to a file without .json extension raises ValueError."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    invalid_path = tmp_path / "dataset.txt"
    
    with pytest.raises(ValueError, match="File must have .json extension"):
        dataset.save(path=str(invalid_path))


def test_save_creates_parent_directories(raw_json_file, tmp_path):
    """Test that save creates parent directories if they don't exist."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    nested_path = tmp_path / "nested" / "dirs" / "dataset.json"
    
    dataset.save(path=str(nested_path))
    
    assert nested_path.exists()


def test_save_and_reload_preserves_data(raw_json_file, tmp_path):
    """Test that saved data can be reloaded correctly."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    save_path = tmp_path / "reload_test.json"
    
    original_len = len(dataset)
    original_agents = dataset.agents
    
    dataset.save(path=str(save_path))
    reloaded = EvaluationDataset(path=str(save_path))
    
    assert len(reloaded) == original_len
    assert reloaded.agents == original_agents
    assert reloaded.identifier == dataset.identifier
    assert reloaded.name == dataset.name


# ================= Delete Method Tests =================


def test_delete_existing_agent(raw_json_file):
    """Test deleting an existing agent's data points."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    original_count = len(dataset)
    
    dataset.delete("agent1")
    
    assert "agent1" not in dataset.agents
    assert len(dataset) == original_count - 2


def test_delete_nonexistent_agent(raw_json_file):
    """Test deleting a non-existent agent logs warning but doesn't error."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    original_count = len(dataset)
    
    dataset.delete("nonexistent_agent")
    
    # Should not affect the dataset
    assert len(dataset) == original_count


# ================= Dunder Method Tests =================


def test_len_returns_total_data_points(raw_json_file):
    """Test __len__ returns the total number of data points."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    assert len(dataset) == 3


def test_len_with_empty_dataset(tmp_path):
    """Test __len__ with an empty dataset."""
    empty_file = tmp_path / "empty.json"
    with open(empty_file, "w", encoding="utf-8") as f:
        json.dump([], f)
    
    dataset = EvaluationDataset(path=str(empty_file))
    
    assert len(dataset) == 0


def test_getitem_returns_agent_data_points(raw_json_file):
    """Test __getitem__ returns data points for an agent."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    agent1_data = dataset["agent1"]
    
    assert isinstance(agent1_data, list)
    assert len(agent1_data) == 2
    assert all(dp.agent_name == "agent1" for dp in agent1_data)


def test_getitem_returns_copy(raw_json_file):
    """Test __getitem__ returns a copy that doesn't affect the original."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    agent1_data = dataset["agent1"]
    original_count = len(dataset["agent1"])
    
    # Modify the returned list
    agent1_data.clear()
    
    # Original should be unchanged
    assert len(dataset["agent1"]) == original_count


def test_getitem_with_nonexistent_agent(raw_json_file):
    """Test __getitem__ with a non-existent agent returns empty list."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    result = dataset["nonexistent_agent"]
    
    assert result == []


# ================= Agent Name Validation Tests =================


def test_dataset_validates_agent_name_mismatch(tmp_path):
    """Test that loading dataset with mismatched agent names skips the malformed data point."""
    file_path = tmp_path / "mismatch.json"
    
    # Create a dataset file with mismatched agent names
    dataset_dict = {
        "metadata": {
            "identifier": "12345678-1234-5678-1234-567812345678",
            "name": "test_dataset",
        },
        "data_points": {
            "agent1": [
                {
                    "agent_name": "agent2",  # Mismatch!
                    "agent_input": {"query": "test"},
                    "agent_output": "output",
                }
            ],
        },
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(dataset_dict, f)
    
    # The malformed data point should be skipped with a warning
    dataset = EvaluationDataset(path=str(file_path))
    
    # Dataset should be empty since the only data point was malformed
    assert len(dataset) == 0
    assert "agent1" not in dataset.agents


# ================= Edge Cases and Integration Tests =================


def test_workflow_create_insert_save_reload(tmp_path):
    """Test a complete workflow: create, insert, save, and reload."""
    # Create initial dataset
    initial_file = tmp_path / "initial.json"
    with open(initial_file, "w", encoding="utf-8") as f:
        json.dump([], f)
    
    dataset = EvaluationDataset(path=str(initial_file), name="workflow_test")
    
    # Insert data points
    dataset.insert([
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "q1"},
            agent_output="a1",
        ),
        AgentDataPoint(
            agent_name="agent1",
            agent_input={"query": "q2"},
            agent_output="a2",
        ),
    ])
    
    # Save to a new location
    save_path = tmp_path / "workflow_saved.json"
    dataset.save(path=str(save_path))
    
    # Reload and verify
    reloaded = EvaluationDataset(path=str(save_path))
    assert len(reloaded) == 2
    assert reloaded.name == "workflow_test"
    assert "agent1" in reloaded.agents


def test_multiple_operations_on_dataset(raw_json_file):
    """Test multiple operations in sequence."""
    dataset = EvaluationDataset(path=str(raw_json_file))
    
    # Sample
    sample = dataset.sample("agent1", n=1)
    assert len(sample) == 1
    
    # Insert
    dataset.insert(AgentDataPoint(
        agent_name="agent3",
        agent_input={"x": 1},
        agent_output="y",
    ))
    assert "agent3" in dataset.agents
    
    # Delete
    dataset.delete("agent2")
    assert "agent2" not in dataset.agents
    
    # Verify final state
    assert len(dataset) == 3  # 2 from agent1 + 1 from agent3


def test_dataset_with_agent_internals(tmp_path):
    """Test dataset handles data points with agent_internals field."""
    data_point = AgentDataPoint(
        agent_name="agent1",
        agent_input={"query": "test"},
        agent_output="output",
        agent_internals={"step_count": 5, "tokens_used": 100},
    )
    
    file_path = tmp_path / "with_internals.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([data_point.model_dump(mode="json")], f)
    
    dataset = EvaluationDataset(path=str(file_path))
    
    assert len(dataset) == 1
    loaded_point = dataset["agent1"][0]
    assert loaded_point.agent_internals == {"step_count": 5, "tokens_used": 100}
