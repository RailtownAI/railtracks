import inspect
import types
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple, Union

from pydantic import BaseModel

from .docstring_parser import param_from_python_type
from .parameters import (
    ArrayParameter,
    ObjectParameter,
    Parameter,
    ParameterType,
    UnionParameter,
)
from .schema_parser import parse_model_properties


class ParameterHandler(ABC):
    """Base abstract class for parameter handlers."""

    @abstractmethod
    def can_handle(self, param_annotation: Any) -> bool:
        pass

    @abstractmethod
    def create_parameter(
        self,
        param_name: str,
        param_annotation: Any,
        description: Optional[str],
        required: bool,
    ) -> Parameter:
        pass


class UnionParameterHandler(ParameterHandler):
    """Handler for Union parameters. Since Optional[x] = Union[x, None]."""

    def can_handle(self, param_annotation: Any) -> bool:
        # Check for typing.Union or Python 3.10+ union (e.g. str | int)
        if (
            hasattr(param_annotation, "__origin__")
            and param_annotation.__origin__ is Union
        ):
            return True
        if isinstance(param_annotation, types.UnionType):
            return True
        return False

    def create_parameter(
        self,
        param_name: str,
        param_annotation: Any,
        description: Optional[str],
        required: bool,
    ) -> Parameter:
        union_args = getattr(param_annotation, "__args__", [])
        options = []
        is_optional = False
        for t in union_args:
            if t is type(None):
                is_optional = True
            else:
                # Recursively parse each option as a Parameter instance
                option_param = param_from_python_type(t)
                options.append(option_param)

        # If no options parsed (e.g. all None?), fallback to DefaultParameter 'none'
        if not options:
            options.append(
                Parameter(
                    name=param_name,
                    param_type="none",
                    description=description,
                    required=required,
                )
            )

        return UnionParameter(
            name=param_name,
            options=options,
            description=description,
            required=required and not is_optional,
        )


class PydanticModelHandler(ParameterHandler):
    """Handler for Pydantic model parameters."""

    def can_handle(self, param_annotation: Any) -> bool:
        return inspect.isclass(param_annotation) and issubclass(
            param_annotation, BaseModel
        )

    def create_parameter(
        self,
        param_name: str,
        param_annotation: Any,
        description: Optional[str],
        required: bool,
    ) -> Parameter:
        schema = param_annotation.model_json_schema()
        inner_params = parse_model_properties(schema)

        # Use ObjectParameter instead of deprecated PydanticParameter
        return ObjectParameter(
            name=param_name,
            properties=inner_params,
            description=description,
            required=required,
            additional_properties=schema.get("additionalProperties", False),
            default=schema.get("default"),
        )


class SequenceParameterHandler(ParameterHandler):
    """Handler for sequence parameters (lists and tuples)."""

    def can_handle(self, param_annotation: Any) -> bool:
        if hasattr(param_annotation, "__origin__"):
            return param_annotation.__origin__ in (list, tuple)
        return param_annotation in (list, tuple, List, tuple)

    def create_parameter(
        self,
        param_name: str,
        param_annotation: Any,
        description: Optional[str],
        required: bool,
    ) -> Parameter:
        is_tuple = False
        if hasattr(param_annotation, "__origin__"):
            is_tuple = param_annotation.__origin__ is tuple
        else:
            is_tuple = param_annotation in (tuple, Tuple)

        sequence_args = getattr(param_annotation, "__args__", [])

        if is_tuple:
            # For tuple of multiple types, fallback to UnionParameter of those types
            options = []
            for idx, t in enumerate(sequence_args):
                options.append(
                    param_from_python_type(
                        t,
                        f"{param_name}_tuple_option_{idx}",
                        f"Option {idx} of tuple",
                        True,
                    )
                )
            # Create UnionParameter to capture all possible tuple element types
            return UnionParameter(
                name=f"{param_name}_tuple_options",
                options=options,
                description=f"{description} (tuple of multiple types)"
                if description
                else None,
                required=required,
            )
        else:
            # For lists, single element type
            if sequence_args:
                element_type = sequence_args[0]

                # If element type is a Pydantic model:
                if inspect.isclass(element_type) and issubclass(
                    element_type, BaseModel
                ):
                    schema = element_type.model_json_schema()
                    inner_params = parse_model_properties(schema)

                    return ArrayParameter(
                        name=param_name,
                        items=ObjectParameter(
                            name=f"{param_name}_item",
                            properties=inner_params,
                            description=f"Item of type {element_type.__name__}",
                            required=True,
                        ),
                        description=description,
                        required=required,
                        max_items=None,
                        additional_properties=False,
                    )
                else:
                    # Primitive or other single type element
                    item_param = param_from_python_type(
                        element_type, f"{param_name}_item", description, True
                    )
                    return ArrayParameter(
                        name=param_name,
                        items=item_param,
                        description=description,
                        required=required,
                        max_items=None,
                        additional_properties=False,
                    )
            else:
                # No specified element type, generic array
                return ArrayParameter(
                    name=param_name,
                    items=Parameter(
                        name=param_name + "_item",
                        param_type=ParameterType.STRING.value,
                        description=description,
                        required=True,
                    ),
                    description=description,
                    required=required,
                    max_items=None,
                    additional_properties=False,
                )


class DefaultParameterHandler(ParameterHandler):
    """Default handler for primitive types and unknown types."""

    def can_handle(self, param_annotation: Any) -> bool:
        return True  # fallback always true

    def create_parameter(
        self,
        param_name: str,
        param_annotation: Any,
        description: Optional[str],
        required: bool,
    ) -> Parameter:
        if isinstance(param_annotation, Parameter):
            return param_annotation  # pass-through if already a Parameter

        mapped_type = ParameterType.from_python_type(param_annotation).value
        return Parameter(
            name=param_name,
            param_type=mapped_type,
            description=description,
            required=required,
        )
