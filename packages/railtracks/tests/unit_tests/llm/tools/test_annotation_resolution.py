"""Tests for annotation resolution when building tool schemas from a signature.

Covers the schema degradation described in issue #1458: under PEP 563 every
parameter used to collapse to ``{"type": "object"}``, and ``Literal`` / nested
generics were mis-derived even without the ``__future__`` import.
"""

import enum
import inspect
import json
import warnings
from typing import Dict, List, Literal, Optional, Tuple, Union

import pytest
import railtracks as rt
from pydantic import BaseModel
from railtracks.exceptions.errors import NodeCreationError
from railtracks.llm.tools.annotations import resolved_signature
from railtracks.llm.tools.parameters import ArrayParameter, ObjectParameter, Parameter
from railtracks.llm.tools.schema_parser import parse_json_schema_to_parameter
from railtracks.llm.tools.tool import Tool

from . import _pep563_module as pep563


def _params(func) -> Dict[str, Parameter]:
    """Return the inferred parameters of ``func`` keyed by name."""
    return {p.name: p for p in Tool.from_function(func).parameters}


def _schema(func, name: str) -> dict:
    """Return the JSON schema inference produces for a single parameter."""
    return _params(func)[name].to_json_schema()


def _manifest(*specs):
    """Build a ToolManifest from ``(name, json_type, required)`` triples."""
    return rt.ToolManifest(
        "Search files.",
        [
            parse_json_schema_to_parameter(name, {"type": json_type}, required)
            for name, json_type, required in specs
        ],
    )


# ================================ resolved_signature ================================


def test_resolved_signature_evaluates_string_annotations():
    resolved = resolved_signature(pep563.search_files)

    assert resolved.parameters["pattern"].annotation is str
    assert resolved.parameters["limit"].annotation is int


def test_resolved_signature_is_untouched_when_nothing_is_deferred():
    def plain(a: str, b: int = 1) -> str:
        return ""

    assert resolved_signature(plain) == inspect.signature(plain)


def test_resolved_signature_keeps_defaults():
    resolved = resolved_signature(pep563.search_files)

    assert resolved.parameters["limit"].default == 10
    assert resolved.parameters["pattern"].default is inspect.Parameter.empty


def test_resolved_signature_warns_and_degrades_on_unresolvable_name():
    with pytest.warns(UserWarning, match="Could not resolve type annotations"):
        resolved = resolved_signature(pep563.unresolvable)

    # left as the original string rather than raising
    assert resolved.parameters["value"].annotation == "DefinitelyNotDefined"


def test_resolved_signature_handles_bound_methods():
    class Calc:
        def add(self, a: "int", b: "int") -> int:
            return a + b

    resolved = resolved_signature(Calc().add)

    assert resolved.parameters["a"].annotation is int
    assert resolved.parameters["b"].annotation is int


# ================================ PEP 563 inference ================================


def test_pep563_primitives_are_not_objects():
    params = _params(pep563.search_files)

    assert params["pattern"].param_type == "string"
    assert params["limit"].param_type == "integer"


def test_pep563_descriptions_still_come_from_the_docstring():
    assert _params(pep563.search_files)["pattern"].description == "Regex to search for."


def test_pep563_required_flag_follows_defaults():
    params = _params(pep563.search_files)

    assert params["pattern"].required is True
    assert params["limit"].required is False


def test_pep563_literal_and_generics_resolve():
    params = _params(pep563.deferred_generics)

    assert params["mode"].to_json_schema()["type"] == "string"
    assert params["tags"].to_json_schema()["type"] == "array"
    assert params["depth"].to_json_schema()["type"] == "integer"


def test_pep563_pydantic_model_resolves_to_object_with_properties():
    origin = _params(pep563.deferred_generics)["origin"]

    assert isinstance(origin, ObjectParameter)
    assert {p.name for p in origin.properties} == {"x", "y"}


def test_pep563_unresolvable_annotation_falls_back_to_object():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        params = _params(pep563.unresolvable)

    assert params["value"].param_type == "object"


# ================================ Literal ================================


def test_literal_becomes_string_with_enum():
    def func(mode: Literal["content", "files"]) -> str:
        """Search.

        Args:
            mode: Where to search.
        """
        return ""

    assert _schema(func, "mode") == {
        "type": "string",
        "description": "Where to search.",
        "enum": ["content", "files"],
    }


def test_literal_of_ints_becomes_integer_with_enum():
    def func(level: Literal[1, 2, 3]) -> str:
        return ""

    schema = _schema(func, "level")

    assert schema["type"] == "integer"
    assert schema["enum"] == [1, 2, 3]


def test_literal_of_mixed_types_lists_every_type():
    def func(value: Literal["a", 1]) -> str:
        return ""

    schema = _schema(func, "value")

    assert set(schema["type"]) == {"string", "integer"}
    assert schema["enum"] == ["a", 1]


def test_optional_literal_keeps_the_enum():
    def func(mode: Optional[Literal["content", "files"]] = None) -> str:
        return ""

    schema = _schema(func, "mode")

    assert schema["type"] == "string"
    assert schema["enum"] == ["content", "files"]


def test_literal_inside_a_list_keeps_the_enum():
    def func(modes: List[Literal["a", "b"]]) -> str:
        return ""

    schema = _schema(func, "modes")

    assert schema["type"] == "array"
    assert schema["items"]["enum"] == ["a", "b"]


def test_literal_over_enum_members_uses_their_values():
    class Colour(enum.Enum):
        RED = "red"
        BLUE = "blue"

    def func(shade: Literal[Colour.RED, Colour.BLUE]) -> str:
        return ""

    schema = _schema(func, "shade")

    assert schema["type"] == "string"
    assert schema["enum"] == ["red", "blue"]


def test_literal_over_enum_members_stays_json_serialisable():
    class Colour(enum.Enum):
        RED = "red"

    def func(shade: Literal[Colour.RED]) -> str:
        return ""

    # a raw enum member in `enum` would raise here, and again when sent to a provider
    json.dumps(_schema(func, "shade"))


# ================================ unschematisable models ================================


def test_bare_basemodel_parameter_degrades_instead_of_raising():
    with pytest.warns(UserWarning, match="Could not derive a JSON schema"):
        params = _params(_takes_bare_model)

    schema = params["value"].to_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True


def test_list_of_bare_basemodel_degrades_instead_of_raising():
    with pytest.warns(UserWarning, match="Could not derive a JSON schema"):
        params = _params(_takes_bare_models)

    schema = params["values"].to_json_schema()
    assert schema["type"] == "array"
    assert schema["items"]["additionalProperties"] is True


def _takes_bare_model(value: BaseModel) -> str:
    """Take any model.

    Args:
        value: Any model.
    """
    return ""


def _takes_bare_models(values: List[BaseModel]) -> str:
    """Take any models.

    Args:
        values: Any models.
    """
    return ""


# ================================ generics inside unions ================================


def test_optional_list_of_str_is_a_typed_array():
    def func(tags: List[str] | None = None) -> str:
        """Tag search.

        Args:
            tags: Tags to filter on.
        """
        return ""

    assert _schema(func, "tags") == {
        "type": "array",
        "items": {"type": "string"},
        "description": "Tags to filter on.",
    }


def test_optional_list_of_str_is_not_required():
    def func(tags: List[str] | None = None) -> str:
        return ""

    assert _params(func)["tags"].required is False


def test_optional_scalar_collapses_to_the_scalar_schema():
    def func(depth: Optional[int] = None) -> str:
        return ""

    assert _schema(func, "depth")["type"] == "integer"


def test_multi_arm_union_keeps_anyof_with_resolved_arms():
    def func(value: Union[List[str], int]) -> str:
        return ""

    schema = _schema(func, "value")

    assert {"type": "array", "items": {"type": "string"}} in schema["anyOf"]
    assert {"type": "integer"} in schema["anyOf"]


def test_optional_pydantic_model_keeps_its_properties():
    class Point(BaseModel):
        x: int
        y: int

    def func(origin: Optional[Point] = None) -> str:
        return ""

    schema = _schema(func, "origin")

    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"x", "y"}


def test_nested_list_of_lists_resolves_both_levels():
    def func(grid: List[List[int]]) -> str:
        return ""

    assert _schema(func, "grid")["items"] == {
        "type": "array",
        "items": {"type": "integer"},
    }


def test_union_containing_a_tuple_does_not_nest_unions():
    def func(value: Union[Tuple[str, int], bool]) -> str:
        return ""

    # a nested UnionParameter would raise TypeError during construction
    assert {"type": "boolean"} in _schema(func, "value")["anyOf"]


def test_array_of_models_still_describes_the_item():
    class Point(BaseModel):
        x: int

    def func(points: List[Point]) -> str:
        return ""

    param = _params(func)["points"]

    assert isinstance(param, ArrayParameter)
    assert isinstance(param.items, ObjectParameter)


# ================================ validate_function ================================


def test_dict_parameter_is_still_rejected_under_pep563():
    with pytest.raises(NodeCreationError):
        rt.function_node(pep563.takes_a_dict)


# ================================ manifest validation ================================


def test_correct_manifest_is_accepted_under_pep563():
    node = rt.function_node(
        pep563.search_files,
        manifest=_manifest(("pattern", "string", True), ("limit", "integer", False)),
    )

    assert {p.name: p.param_type for p in node.node_type.tool_info().parameters} == {
        "pattern": "string",
        "limit": "integer",
    }


def test_manifest_matching_literal_and_generic_parameters_is_accepted():
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        rt.function_node(
            pep563.deferred_generics,
            manifest=_manifest(
                ("mode", "string", True),
                ("tags", "array", False),
                ("depth", "integer", False),
                ("origin", "object", False),
            ),
        )


def test_manifest_type_mismatch_warns_instead_of_raising():
    def func(a: int) -> str:
        """Take an int.

        Args:
            a: A number.
        """
        return ""

    with pytest.warns(UserWarning, match="Type mismatch for parameter 'a'"):
        node = rt.function_node(func, manifest=_manifest(("a", "string", True)))

    # the manifest, not the inference, is what reaches the model
    assert node.node_type.tool_info().parameters[0].param_type == "string"


def test_unannotated_parameter_does_not_constrain_the_manifest():
    def func(a) -> str:
        """Take anything.

        Args:
            a: Anything.
        """
        return ""

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        rt.function_node(func, manifest=_manifest(("a", "string", True)))


def test_str_subclass_annotation_does_not_constrain_the_manifest():
    class DomainStr(str):
        pass

    def func(a: DomainStr) -> str:
        """Take a domain string.

        Args:
            a: A domain string.
        """
        return ""

    # the type mapping is an identity lookup, so a str subclass only reaches the
    # generic object fallback; the manifest is the more accurate description
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        rt.function_node(func, manifest=_manifest(("a", "string", True)))


def test_unrecognised_class_annotation_does_not_constrain_the_manifest():
    class Widget:
        pass

    def func(a: Widget) -> str:
        """Take a widget.

        Args:
            a: A widget.
        """
        return ""

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        rt.function_node(func, manifest=_manifest(("a", "array", True)))


def test_manifest_parameter_missing_from_signature_still_raises():
    with pytest.raises(NodeCreationError, match="does not exist in function signature"):
        rt.function_node(
            pep563.search_files,
            manifest=_manifest(("pattern", "string", True), ("nope", "string", True)),
        )


def test_required_parameter_missing_from_manifest_still_raises():
    with pytest.raises(NodeCreationError, match="missing from tool manifest"):
        rt.function_node(
            pep563.search_files, manifest=_manifest(("limit", "integer", False))
        )
