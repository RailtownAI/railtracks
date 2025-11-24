import json
import pytest
from pathlib import Path
from uuid import UUID
from pydantic import BaseModel
from railtracks.evaluation.data.local import LocalDataset
from railtracks.evaluation.data.point import DataPoint


class MockOutput(BaseModel):
    result: str
    confidence: float


@pytest.fixture
def sample_datapoints():
    return [
        DataPoint(agent_input="input1", agent_output="output1", expected_output="expected1"),
        DataPoint(agent_input="input2", agent_output="output2", expected_output="expected2"),
    ]


@pytest.fixture
def temp_json_file(tmp_path):
    return tmp_path / "test_dataset.json"


def test_init_empty():
    ds = LocalDataset()
    assert len(ds) == 0
    assert ds.data_points == []


def test_init_with_datapoints(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    assert len(ds) == 2
    assert all(dp in ds.data_points for dp in sample_datapoints)


def test_insert_single_datapoint():
    ds = LocalDataset()
    dp = DataPoint(agent_input="test", agent_output="output")
    ds.insert(dp)
    assert len(ds) == 1
    assert ds[dp.identifier] == dp


def test_insert_list_datapoints(sample_datapoints):
    ds = LocalDataset()
    ds.insert(sample_datapoints)
    assert len(ds) == 2


def test_insert_duplicate_raises_error(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    with pytest.raises(ValueError, match="already exists"):
        ds.insert(sample_datapoints[0])


def test_delete_by_datapoint(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    ds.delete(sample_datapoints[0])
    assert len(ds) == 1


def test_delete_by_uuid(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    uuid = sample_datapoints[0].identifier
    ds.delete(uuid)
    assert len(ds) == 1


def test_getitem(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    dp = sample_datapoints[0]
    assert ds[dp.identifier] == dp


def test_getitem_missing_raises_keyerror():
    ds = LocalDataset()
    with pytest.raises(KeyError):
        ds[UUID("12345678-1234-5678-1234-567812345678")]


def test_sample_full_dataset(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    sampled = ds.sample(5)
    assert len(sampled) == 2


def test_sample_subset(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    sampled = ds.sample(1)
    assert len(sampled) == 1
    assert sampled[0] in sample_datapoints


def test_save_and_load(temp_json_file, sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    ds.save(str(temp_json_file))
    
    assert temp_json_file.exists()
    
    loaded = LocalDataset(path=str(temp_json_file))
    assert len(loaded) == 2
    assert loaded.data_points[0].agent_input in ["input1", "input2"]


def test_save_invalid_extension():
    ds = LocalDataset()
    with pytest.raises(ValueError, match=".json extension"):
        ds.save("test.csv")


def test_load_invalid_extension(tmp_path):
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("test")
    with pytest.raises(ValueError, match="Only .json is supported"):
        LocalDataset(path=str(bad_file))


def test_load_missing_file():
    with pytest.raises(ValueError, match="File not found"):
        LocalDataset(path="nonexistent.json")


def test_load_invalid_json_structure(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text('{"not": "a list"}')
    with pytest.raises(ValueError, match="must contain a list"):
        LocalDataset(path=str(bad_json))


def test_context_manager_with_auto_save(temp_json_file, sample_datapoints):
    ds = LocalDataset(auto_save=True)
    ds._path = str(temp_json_file)
    with ds:
        ds.insert(sample_datapoints)
    
    assert temp_json_file.exists()
    loaded = LocalDataset(path=str(temp_json_file))
    assert len(loaded) == 2


def test_context_manager_without_auto_save(temp_json_file):
    ds = LocalDataset(auto_save=False)
    ds._path = str(temp_json_file)
    with ds:
        ds.insert(DataPoint(agent_input="test", agent_output="output"))
    
    assert not temp_json_file.exists()


def test_data_points_property(sample_datapoints):
    ds = LocalDataset(data_points=sample_datapoints)
    points = ds.data_points
    assert isinstance(points, list)
    assert len(points) == 2


def test_uuid_serialization_roundtrip(temp_json_file):
    dp = DataPoint(
        agent_input="test",
        agent_output="output",
        identifier=UUID("12345678-1234-5678-1234-567812345678")
    )
    ds = LocalDataset(data_points=[dp])
    ds.save(str(temp_json_file))
    
    loaded = LocalDataset(path=str(temp_json_file))
    assert loaded.data_points[0].identifier == dp.identifier


def test_save_basemodel_output(temp_json_file):
    mock_output = MockOutput(result="success", confidence=0.95)
    dp = DataPoint(
        agent_input="test",
        agent_output=mock_output,
        expected_output=MockOutput(result="expected", confidence=1.0)
    )
    ds = LocalDataset(data_points=[dp])
    ds.save(str(temp_json_file))
    
    with open(temp_json_file) as f:
        data = json.load(f)
    
    # Verify BaseModel is serialized as dict with proper fields
    assert isinstance(data[0]["agent_output"], dict)
    assert data[0]["agent_output"]["result"] == "success"
    assert data[0]["agent_output"]["confidence"] == 0.95
    assert data[0]["expected_output"]["result"] == "expected"
    assert data[0]["expected_output"]["confidence"] == 1.0
