from uuid import UUID
from pydantic import BaseModel
import pytest
from railtracks.evaluation.data.point import DataPoint


class MockModel(BaseModel):
    value: str


def test_datapoint_creation_with_strings():
    dp = DataPoint(agent_input="test input", agent_output="test output")
    assert dp.agent_input == "test input"
    assert dp.agent_output == "test output"
    assert dp.expected_output is None
    assert isinstance(dp.identifier, UUID)


def test_datapoint_with_expected_output():
    dp = DataPoint(
        agent_input="input",
        agent_output="output",
        expected_output="expected"
    )
    assert dp.expected_output == "expected"


def test_datapoint_with_basemodel_output():
    model = MockModel(value="test")
    dp = DataPoint(agent_input="input", agent_output=model)
    assert isinstance(dp.agent_output, MockModel)
    assert dp.agent_output.value == "test"


def test_datapoint_with_basemodel_expected():
    model = MockModel(value="expected")
    dp = DataPoint(
        agent_input="input",
        agent_output="output",
        expected_output=model
    )
    assert isinstance(dp.expected_output, MockModel)


def test_datapoint_custom_identifier():
    custom_id = UUID("12345678-1234-5678-1234-567812345678")
    dp = DataPoint(
        agent_input="input",
        agent_output="output",
        identifier=custom_id
    )
    assert dp.identifier == custom_id


def test_datapoint_unique_identifiers():
    dp1 = DataPoint(agent_input="input1", agent_output="output1")
    dp2 = DataPoint(agent_input="input2", agent_output="output2")
    assert dp1.identifier != dp2.identifier
