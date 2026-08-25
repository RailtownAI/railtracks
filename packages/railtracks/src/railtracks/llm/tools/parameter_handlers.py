import enum
import inspect
import types
import warnings
from abc import ABC, abstractmethod
from typing import Any, List, Literal, Optional, Tuple, Union, get_args, get_origin

from pydantic import BaseModel

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
        options: List[Parameter] = []
        is_optional = False
        for t in union_args:
            if t is type(None):
                is_optional = True
            else:
                # Dispatch through the full chain so nested generics, literals and
                # models keep their structure instead of collapsing to 'object'.
                options.append(build_parameter(param_annotation=t))

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

        options = _flatten_union_options(options)

        if len(options) == 1:
            # `Optional[X]` is a union in name only; emit X's schema directly rather
            # than a single-branch anyOf. Optionality is carried by `required`.
            only = options[0]
            only.name = param_name
            only.description = description or only.description
            only.required = required and not is_optional
            return only

        return UnionParameter(
            name=param_name,
            options=options,
            description=description,
            required=required and not is_optional,
        )


def _model_object_parameter(
    model: Any,
    param_name: str,
    description: Optional[str],
    required: bool,
) -> ObjectParameter:
    """Describe a pydantic model as an :class:`ObjectParameter`.

    Not every ``BaseModel`` subclass can produce a schema: ``BaseModel`` itself,
    an unparametrised generic model, or a model with unresolvable forward
    references all raise. A tool should still be creatable in those cases, so the
    parameter degrades to an open object rather than propagating the error.

    Args:
        model: The ``BaseModel`` subclass to describe.
        param_name: Name to give the resulting parameter.
        description: Description to attach.
        required: Whether the parameter is required.

    Returns:
        An ``ObjectParameter``, with enumerated properties when a schema was
        available and an open object when it was not.
    """
    try:
        schema = model.model_json_schema()
    except Exception as exc:  # noqa: BLE001 any schema failure degrades the same way
        warnings.warn(
            f"Could not derive a JSON schema for '{getattr(model, '__name__', model)}' "
            f"(parameter '{param_name}'): {exc}. Falling back to an unconstrained "
            "object; pass an explicit ToolManifest to describe this parameter.",
            UserWarning,
            stacklevel=4,
        )
        return ObjectParameter(
            name=param_name,
            properties=[],
            description=description,
            required=required,
            additional_properties=True,
        )

    return ObjectParameter(
        name=param_name,
        properties=parse_model_properties(schema),
        description=description,
        required=required,
        additional_properties=schema.get("additionalProperties", False),
        default=schema.get("default"),
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
        # ObjectParameter, not the deprecated PydanticParameter
        return _model_object_parameter(
            param_annotation, param_name, description, required
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
                    build_parameter(
                        param_name=f"{param_name}_tuple_option_{idx}",
                        param_annotation=t,
                        description=f"Option {idx} of tuple",
                    )
                )
            # Create UnionParameter to capture all possible tuple element types
            return UnionParameter(
                name=f"{param_name}_tuple_options",
                options=_flatten_union_options(options),
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
                    return ArrayParameter(
                        name=param_name,
                        items=_model_object_parameter(
                            element_type,
                            f"{param_name}_item",
                            f"Item of type {element_type.__name__}",
                            True,
                        ),
                        description=description,
                        required=required,
                        max_items=None,
                        additional_properties=False,
                    )
                else:
                    # Primitive, literal, generic or union element type
                    item_param = build_parameter(
                        param_name=f"{param_name}_item",
                        param_annotation=element_type,
                        description=description,
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


class LiteralParameterHandler(ParameterHandler):
    """Handler for ``Literal[...]`` parameters, which map to an enum-constrained type."""

    def can_handle(self, param_annotation: Any) -> bool:
        return get_origin(param_annotation) is Literal

    def create_parameter(
        self,
        param_name: str,
        param_annotation: Any,
        description: Optional[str],
        required: bool,
    ) -> Parameter:
        # `Literal` also admits enum members; those must be unwrapped or the schema
        # carries objects a JSON encoder cannot serialise.
        values = [
            v.value if isinstance(v, enum.Enum) else v
            for v in get_args(param_annotation)
        ]

        # JSON schema constrains a literal by value; the type is whatever the
        # values happen to be, which is a single type in all but exotic cases.
        value_types = []
        for value in values:
            mapped = ParameterType.from_python_type(type(value)).value
            if mapped not in value_types:
                value_types.append(mapped)

        if not value_types:
            param_type: Any = ParameterType.STRING.value
        elif len(value_types) == 1:
            param_type = value_types[0]
        else:
            param_type = value_types

        return Parameter(
            name=param_name,
            param_type=param_type,
            description=description,
            required=required,
            enum=values,
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


def _flatten_union_options(options: List[Parameter]) -> List[Parameter]:
    """Expand nested :class:`UnionParameter` options into a flat list.

    ``UnionParameter`` rejects unions inside its own options, and nesting can arise
    from annotations such as ``Union[Tuple[str, int], bool]``.

    Args:
        options: Parameters destined for a ``UnionParameter``.

    Returns:
        The same parameters with any union members replaced by their own options.
    """
    flattened: List[Parameter] = []
    for option in options:
        if isinstance(option, UnionParameter):
            flattened.extend(_flatten_union_options(option.options))
        else:
            flattened.append(option)
    return flattened


def default_handlers() -> List[ParameterHandler]:
    """Return the handler chain used to turn an annotation into a :class:`Parameter`.

    Order matters: the first handler whose ``can_handle`` returns ``True`` wins, and
    :class:`DefaultParameterHandler` accepts everything, so it must stay last.

    Returns:
        A freshly built list of handlers, most specific first.
    """
    return [
        PydanticModelHandler(),
        LiteralParameterHandler(),
        SequenceParameterHandler(),
        UnionParameterHandler(),
        DefaultParameterHandler(),
    ]


def build_parameter(
    param_annotation: Any,
    param_name: str = "",
    description: Optional[str] = None,
    required: bool = True,
) -> Parameter:
    """Build a :class:`Parameter` from a resolved Python annotation.

    Args:
        param_annotation: The annotation to convert. Must already be a real type;
            string annotations should be resolved first
            (see :func:`railtracks.llm.tools.annotations.resolved_signature`).
        param_name: Name to give the resulting parameter.
        description: Description to attach, typically taken from the docstring.
        required: Whether the parameter is required.

    Returns:
        The most specific ``Parameter`` subclass that fits ``param_annotation``.
    """
    handler = next(h for h in default_handlers() if h.can_handle(param_annotation))
    return handler.create_parameter(param_name, param_annotation, description, required)
