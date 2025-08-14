import time

import pytest
from typing import List, Tuple, Dict, Any
from pydantic import BaseModel
from railtracks.llm.type_mapping import TypeMapper


class DummyModel(BaseModel):
    a: int
    b: str


def dummy_func(a: int, b: str, c: float, d: DummyModel, e: List[int], f: Tuple[str, int]):
    pass


def dummy_func_with_dict(a: Dict[str, str]):
    pass


@pytest.fixture
def type_mapper():
    return TypeMapper(dummy_func)


@pytest.mark.parametrize(
    "input_value,target_type,expected",
    [
        ("123", int, 123),
        ("45.6", float, 45.6),
        ("test", str, "test"),
        (None, Any, None),
    ],
)
def test_convert_value_basic_types(input_value, target_type, expected):
    assert TypeMapper._convert_value(input_value, target_type) == expected


def test_convert_kwargs_to_appropriate_types(type_mapper):
    kwargs = {
        "a": "1",
        "b": "text",
        "c": "3.5",
        "d": {"a": 10, "b": "foo"},
        "e": ["1", "2", "3"],
        "f": ("foo", "2"),
    }
    converted = type_mapper.convert_kwargs_to_appropriate_types(kwargs)

    assert converted["a"] == 1
    assert converted["b"] == "text"
    assert converted["c"] == 3.5
    assert isinstance(converted["d"], DummyModel)
    assert converted["d"].a == 10
    assert converted["d"].b == "foo"
    assert converted["e"] == [1, 2, 3]
    assert converted["f"] == ("foo", 2)


def test_convert_to_sequence_list():
    result = TypeMapper._convert_to_sequence(["1", "2"], list, (int,))
    assert result == [1, 2]


def test_convert_to_sequence_tuple():
    result = TypeMapper._convert_to_sequence(["foo", "2"], tuple, (str, int))
    assert result == ("foo", 2)


def test_convert_to_pydantic_model_success():
    result = TypeMapper._convert_to_pydantic_model({"a": 1, "b": "two"}, DummyModel)
    assert isinstance(result, DummyModel)
    assert result.a == 1
    assert result.b == "two"


def test_convert_to_pydantic_model_failure():
    with pytest.raises(RuntimeError):
        TypeMapper._convert_to_pydantic_model("invalid", DummyModel)


def test_convert_value_dict_error():
    tm = TypeMapper(dummy_func_with_dict)
    with pytest.raises(RuntimeError):
        tm.convert_kwargs_to_appropriate_types({"a": {"key": "value"}})


def test_builtin_function_raises_runtime_error():
    with pytest.raises(RuntimeError):
        TypeMapper(time.sleep)  # time.sleep is a builtin


def test_invalid_conversion_returns_error_message():
    # string can't be converted to int by `int("abc")`
    assert TypeMapper._convert_value("abc", int) == "abc"


def test_convert_to_sequence_wraps_non_sequence_list():
    # Input is a single int string; should wrap into list and convert to int
    result = TypeMapper._convert_to_sequence("5", list, (int,))
    assert result == [5]


def test_convert_to_sequence_wraps_non_sequence_tuple():
    # Input is a single string; should wrap into tuple and convert to str
    result = TypeMapper._convert_to_sequence(5, tuple, (int,))
    assert result == (5,)


