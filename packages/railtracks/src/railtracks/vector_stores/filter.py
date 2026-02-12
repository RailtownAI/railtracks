from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Tuple, Union


class Op(str, Enum):
    """Enumeration of comparison operators for filter predicates."""

    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NIN = "NIN"


class LogicOp(str, Enum):
    """Enumeration of logical operators for combining filter expressions."""

    AND = "AND"
    OR = "OR"


OP_SYMBOL = {
    Op.EQ: "==",
    Op.NE: "!=",
    Op.GT: ">",
    Op.GTE: ">=",
    Op.LT: "<",
    Op.LTE: "<=",
    Op.IN: "in",
    Op.NIN: "not in",
}

LOGIC_SYMBOL = {LogicOp.AND: "&", LogicOp.OR: "|"}

ValidValue = Union[str, int, float, bool, list]


@dataclass(frozen=True)
class Predicate:
    """Atomic condition on a single field with a comparison operator and value.

    Attributes:
        field: The name of the field to compare
        op: The comparison operator to apply
        value: The value to compare against
    """

    field: str
    op: Op
    value: ValidValue

    def __str__(self) -> str:
        if isinstance(self.value, str):
            value = '"' + self.value + '"'
        else:
            value = self.value
        return "(" + f'"{self.field}" {OP_SYMBOL[self.op]} {value}' + ")"


class BaseExpr(ABC):
    """Abstract base class for all filter expressions."""

    def __and__(self, other: BaseExpr) -> BaseExpr:
        """Combine two expressions with logical AND."""
        return and_(self, other)

    def __or__(self, other: BaseExpr) -> BaseExpr:
        """Combine two expressions with logical OR."""
        return or_(self, other)

    def __bool__(self) -> bool:
        """Prevent misuse of expressions in boolean contexts."""
        raise TypeError("Filter expressions cannot be used in boolean contexts")

    @abstractmethod
    def to_ast_dict(self) -> dict:
        """Convert expression to abstract syntax tree dictionary format."""
        pass


@dataclass(frozen=True)
class LeafExpr(BaseExpr):
    """Leaf node in a filter expression tree containing a single predicate."""

    pred: Predicate

    def to_ast_dict(self) -> dict:
        """Convert leaf expression to AST dictionary.

        Returns:
            Dictionary with keys: op="LEAF", field, cmp (operator name), value
        """
        return {
            "op": "LEAF",
            "field": self.pred.field,
            "cmp": self.pred.op.value,
            "value": self.pred.value,
        }

    def __str__(self) -> str:
        return str(self.pred)


@dataclass(frozen=True)
class LogicExpr(BaseExpr):
    """Internal node in a filter expression tree combining multiple sub-expressions.

    Attributes:
        op: The logical operator (AND or OR) combining the children
        children: Tuple of child expressions to combine
    """

    op: LogicOp
    children: Tuple[BaseExpr, ...]

    def __post_init__(self) -> None:
        """Validate that logic expression has at least 2 children.

        Raises:
            ValueError: If fewer than 2 children or unknown operator
        """
        if self.op in LogicOp:
            if len(self.children) < 2:
                raise ValueError(f"{self.op.name} LogicExpr must have >= 2 children")
            if not all(isinstance(c, BaseExpr) for c in self.children):
                raise TypeError(
                    "All children of LogicExpr must be LogicExpr or LeafExpr instances"
                )
        else:
            raise TypeError(f"Unknown LogicOp: {self.op}")

    def to_ast_dict(self) -> dict:
        """Convert logic expression to AST dictionary."""
        return {
            "op": self.op.name,
            "children": [c.to_ast_dict() for c in self.children],
        }

    def __str__(self) -> str:
        expression = "(" + str(self.children[0])
        for i in range(1, len(self.children)):
            expression += f" {LOGIC_SYMBOL[self.op]} " + f"{self.children[i]}"
        return expression + ")"


# ---- Normalizing constructors -----------


def and_(*exprs: BaseExpr) -> LogicExpr:
    """Combine multiple filter expressions with logical AND.

    Automatically flattens nested AND expressions to avoid unnecessary nesting.
    For example: and_(and_(a, b), c) becomes and_(a, b, c).

    Args:
        *exprs: One or more filter expressions to combine

    Returns:
        A LogicExpr representing the AND combination

    Raises:
        ValueError: If no expressions provided or only one expression after flattening
    """
    if not exprs:
        raise ValueError("and_() requires at least one Expression")

    flat: list[BaseExpr] = []
    for e in exprs:
        if isinstance(e, LogicExpr) and e.op == LogicOp.AND:
            flat.extend(e.children)
        else:
            flat.append(e)

    if len(flat) == 1:
        raise ValueError("and_() requires at least two Expressions to form a LogicExpr")

    return LogicExpr(op=LogicOp.AND, children=tuple(flat))


def or_(*exprs: BaseExpr) -> LogicExpr:
    """Combine multiple filter expressions with logical OR.

    Automatically flattens nested OR expressions to avoid unnecessary nesting.
    For example: or_(or_(a, b), c) becomes or_(a, b, c).

    Args:
        *exprs: One or more filter expressions to combine

    Returns:
        A LogicExpr representing the OR combination

    Raises:
        ValueError: If no expressions provided or only one expression after flattening
    """
    if not exprs:
        raise ValueError("or_() requires at least one Expression")

    flat: list[BaseExpr] = []
    for e in exprs:
        if isinstance(e, LogicExpr) and e.op == LogicOp.OR:
            flat.extend(e.children)
        else:
            flat.append(e)

    if len(flat) == 1:
        raise ValueError("or_() requires at least two Expressions to form a LogicExpr")

    return LogicExpr(op=LogicOp.OR, children=tuple(flat))


def all_of(filters: Iterable[BaseExpr]) -> BaseExpr:
    """Combine an iterable of filter expressions with logical AND.

    Args:
        filters: An iterable of filter expressions to combine

    Returns:
        A single filter expression (LeafExpr if one filter, LogicExpr if multiple)

    Raises:
        ValueError: If the iterable is empty
    """
    lst = list(filters)
    if not lst:
        raise ValueError("all_of() requires at least one Expression")

    if len(lst) == 1:
        return lst[0]

    return and_(*lst)


def any_of(filters: Iterable[BaseExpr]) -> BaseExpr:
    """Combine an iterable of filter expressions with logical OR.

    Args:
        filters: An iterable of filter expressions to combine

    Returns:
        A single filter expression (LeafExpr if one filter, LogicExpr if multiple)

    Raises:
        ValueError: If the iterable is empty
    """
    lst = list(filters)
    if not lst:
        raise ValueError("any_of() requires at least one Expression")

    if len(lst) == 1:
        return lst[0]

    return or_(*lst)


class FieldRef:
    """Reference to a field in a filter expression.

    Provides methods for creating predicates on a specific field using various
    comparison operators. Can be obtained via F[field_name] syntax.

    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def _normalize_value(self, value: Any) -> ValidValue:
        """Normalize value for comparison.

        Currently a no-op, but can be extended for type conversions if needed.
        """
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._normalize_value(x) for x in value]

        raise TypeError(f"Unsupported filter value type: {type(value)}")

    def _leaf(self, op: Op, value: Any) -> LeafExpr:
        """Create a leaf expression with the given operator and value."""
        return LeafExpr(
            Predicate(field=self._name, op=op, value=self._normalize_value(value))
        )

    # explicit methods
    def _eq(self, value: Any) -> LeafExpr:
        """Create an equality filter."""
        return self._leaf(Op.EQ, value)

    def _ne(self, value: Any) -> LeafExpr:
        """Create an inequality filter."""
        return self._leaf(Op.NE, value)

    def _gt(self, value: Any) -> LeafExpr:
        """Create a greater-than filter."""
        return self._leaf(Op.GT, value)

    def _gte(self, value: Any) -> LeafExpr:
        """Create a greater-than-or-equal filter."""
        return self._leaf(Op.GTE, value)

    def _lt(self, value: Any) -> LeafExpr:
        """Create a less-than filter."""
        return self._leaf(Op.LT, value)

    def _lte(self, value: Any) -> LeafExpr:
        """Create a less-than-or-equal filter."""
        return self._leaf(Op.LTE, value)

    def is_in(self, values: Iterable[Any]) -> LeafExpr:
        """Create a membership filter.

        Raises:
            ValueError: If the values collection is empty
        """
        vals = list(values)
        if not vals:
            raise ValueError("in_() requires at least one value")
        return self._leaf(Op.IN, vals)

    def not_in(self, values: Iterable[Any]) -> LeafExpr:
        """Create a non-membership filter.

        Raises:
            ValueError: If the values collection is empty
        """
        vals = list(values)
        if not vals:
            raise ValueError("not_in() requires at least one value")
        return self._leaf(Op.NIN, vals)

    # operator sugar
    def __eq__(self, other: Any) -> LeafExpr:
        """Support == operator for equality filters."""
        if isinstance(other, FieldRef):
            raise TypeError("Cannot compare two FieldRef objects for equality")
        return self._eq(other)

    def __ne__(self, other: Any) -> LeafExpr:
        """Support != operator for inequality filters."""
        if isinstance(other, FieldRef):
            raise TypeError("Cannot compare two FieldRef objects for inequality")
        return self._ne(other)

    def __gt__(self, other: Any) -> LeafExpr:
        """Support > operator for greater-than filters."""
        if isinstance(other, FieldRef):
            raise TypeError("Cannot compare two FieldRef objects")
        return self._gt(other)

    def __ge__(self, other: Any) -> LeafExpr:
        """Support >= operator for greater-than-or-equal filters."""
        if isinstance(other, FieldRef):
            raise TypeError("Cannot compare two FieldRef objects")
        return self._gte(other)

    def __lt__(self, other: Any) -> LeafExpr:
        """Support < operator for less-than filters."""
        if isinstance(other, FieldRef):
            raise TypeError("Cannot compare two FieldRef objects")
        return self._lt(other)

    def __le__(self, other: Any) -> LeafExpr:
        """Support <= operator for less-than-or-equal filters."""
        if isinstance(other, FieldRef):
            raise TypeError("Cannot compare two FieldRef objects")
        return self._lte(other)


class _FilterBuilder:
    """Builder class that provides convenient F[field_name] syntax for creating FieldRef objects.

    This class enables the intuitive F["field_name"] syntax for constructing
    filter expressions, which is then used with comparison operators.
    """

    def __getitem__(self, name: str) -> FieldRef:
        """Get a FieldRef for the specified field name."""
        return FieldRef(name)


# Global filter builder instance for convenient filter construction
F = _FilterBuilder()


if __name__ == "__main__":
    a = F["field"] == "Value"
    b = F["age"] > 19

    print(a & b)
