import hashlib
import json
from typing import Annotated, Generic, Literal, TypeVar, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)


def _json_default(value):
    """Fallback serializer for identifier hashing (e.g. Category instances)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(
        f"Object of type {value.__class__.__name__} is not JSON serializable"
    )


class Metric(BaseModel):
    name: str
    metric_type: Literal["Metric"] = "Metric"
    identifier: str = ""
    model_config = ConfigDict(frozen=True)
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _generate_identifier(cls, values):
        """Generate deterministic identifier from configuration."""
        # Only generate identifier if not already provided
        if values.get("identifier", "") != "":
            return values

        config = {k: v for k, v in values.items() if k != "identifier"}
        config["_type"] = cls.__name__

        for key, value in list(config.items()):
            if isinstance(value, type):
                config[key] = value.__name__

        config_str = json.dumps(config, sort_keys=True, default=_json_default)
        identifier = hashlib.sha256(config_str.encode()).hexdigest()

        values["identifier"] = identifier
        return values

    def __hash__(self):
        """Hash by identifier for set/dict key usage."""
        return hash(self.identifier)

    def __eq__(self, other):
        """Equality based on identifier."""
        if not isinstance(other, Metric):
            return False
        return self.identifier == other.identifier

    def __str__(self) -> str:
        """Custom string represention excluding the identifier field"""
        fields = {k: v for k, v in self.model_dump().items() if k != "identifier"}
        fields_str = ", ".join(f"{k}={repr(v)}" for k, v in fields.items())
        return f"{self.__class__.__name__}({fields_str})"


_ALLOWED_CATEGORY_STATUSES = (None, "pass", "fail", "partial")


class Category(BaseModel):
    name: str
    status: Literal["pass", "fail", "partial"] | None = None
    model_config = ConfigDict(frozen=True)

    def model_post_init(self, __context) -> None:
        if self.status not in _ALLOWED_CATEGORY_STATUSES:
            raise ValueError(
                f"Category.status must be one of 'pass', 'fail', 'partial', or None; got {self.status!r}"
            )

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, Category):
            return self.name == other.name
        return NotImplemented

    def __str__(self) -> str:
        return self.name


def _to_category(category: str | Category) -> Category:
    if isinstance(category, str):
        return Category(name=category)
    return category


CategoryLike = Annotated[
    Category | str,
    BeforeValidator(_to_category, json_schema_input_type=str | Category),
]


class Categorical(Metric):
    metric_type: Literal["Categorical"] = "Categorical"  # type: ignore[assignment]
    categories: list[CategoryLike]

    @property
    def category_names(self) -> list[str]:
        return [str(c) for c in self.categories]

    def _names_with_status(self, status: str) -> list[str]:
        return [c.name for c in self.categories if isinstance(c, Category) and c.status == status]

    @computed_field
    @property
    def pass_categories(self) -> list[str]:
        return self._names_with_status("pass")

    @computed_field
    @property
    def fail_categories(self) -> list[str]:
        return self._names_with_status("fail")

    @computed_field
    @property
    def partial_categories(self) -> list[str]:
        return self._names_with_status("partial")

    @field_serializer("categories")
    def _serialize_categories(self, categories: list[CategoryLike]) -> list[str]:
        return [str(c) for c in categories]


T = TypeVar("T", int, float)


class Numerical(Metric, Generic[T]):
    metric_type: Literal["Numerical"] = "Numerical"  # type: ignore[assignment]
    min_value: T | None = None
    max_value: T | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_min_max(cls, values):
        min_value = values.get("min_value")
        max_value = values.get("max_value")
        if min_value is not None and max_value is not None:
            if min_value >= max_value:
                raise ValueError("min_value must be less than max_value")
        return values


class LLMMetric(Numerical):
    """A Numerical metric specific to LLM usage statistics."""

    metric_type: Literal["LLMMetric"] = "LLMMetric"  # type: ignore[assignment]


class ToolMetric(Numerical):
    """A Numerical metric specific to tool usage statistics."""

    metric_type: Literal["ToolMetric"] = "ToolMetric"  # type: ignore[assignment]


METRIC_TYPES = Annotated[
    Union[LLMMetric, ToolMetric, Numerical, Categorical, Metric],
    Field(discriminator="metric_type"),
]
