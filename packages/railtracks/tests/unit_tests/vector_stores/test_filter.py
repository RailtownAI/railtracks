import pytest
from enum import Enum

from railtracks.vector_stores.filter import (
    Op,
    LogicOp,
    LeafExpr,
    LogicExpr,
    F,
    and_,
    or_,
    all_of,
    any_of,
)


class Color(Enum):
    RED = "red"
    BLUE = "blue"


def test_leaf_eq_operator_builds_leafexpr():
    expr = F["age"] == 3
    assert isinstance(expr, LeafExpr)
    assert expr.pred.field == "age"
    assert expr.pred.op == Op.EQ
    assert expr.pred.value == 3


def test_leaf_to_ast_dict_schema():
    expr = F["age"] >= 18
    ast = expr.to_ast_dict()
    assert ast == {"op": "LEAF", "field": "age", "cmp": "GTE", "value": 18}


@pytest.mark.parametrize(
    "expr_builder, expected_op, expected_value",
    [
        (lambda: F["x"] == 1, Op.EQ, 1),
        (lambda: F["x"] != 1, Op.NE, 1),
        (lambda: F["x"] > 1, Op.GT, 1),
        (lambda: F["x"] >= 1, Op.GTE, 1),
        (lambda: F["x"] < 1, Op.LT, 1),
        (lambda: F["x"] <= 1, Op.LTE, 1),
    ],
)
def test_fieldref_comparison_sugar(expr_builder, expected_op, expected_value):
    expr = expr_builder()
    assert isinstance(expr, LeafExpr)
    assert expr.pred.op == expected_op
    assert expr.pred.value == expected_value


def test_fieldref_to_fieldref_comparison_raises():
    a = F["a"]
    b = F["b"]
    with pytest.raises(TypeError):
        _ = a == b
    with pytest.raises(TypeError):
        _ = a != b
    with pytest.raises(TypeError):
        _ = a > b
    with pytest.raises(TypeError):
        _ = a >= b
    with pytest.raises(TypeError):
        _ = a < b
    with pytest.raises(TypeError):
        _ = a <= b


def test_normalize_enum_value():
    expr = F["color"]._eq(Color.RED)
    assert expr.pred.value == "red"


def test_normalize_unsupported_type_raises():
    with pytest.raises(TypeError):
        _ = F["x"]._eq({"nope": "dict"})


def test_in_requires_nonempty():
    with pytest.raises(ValueError):
        _ = F["x"].is_in([])


def test_not_in_requires_nonempty():
    with pytest.raises(ValueError):
        _ = F["x"].not_in([])


def test_in_normalizes_to_list_in_predicate():
    expr = F["x"].is_in([1, 2, 3])
    assert expr.pred.op == Op.IN
    # normalize turns tuples into lists
    assert expr.pred.value == [1, 2, 3]


def test_not_in_normalizes_to_list_in_predicate():
    expr = F["x"].not_in([1, 2, 3])
    assert expr.pred.op == Op.NIN
    assert expr.pred.value == [1, 2, 3]

@pytest.mark.parametrize(
    "value, expected",
    [
        ("hi", "hi"),
        (3, 3),
        (1.5, 1.5),
        (True, True),
        (Color.RED, "red"),
        ([1, 2, 3], [1, 2, 3]),
        ([Color.RED, Color.BLUE], ["red", "blue"]),
    ],
)
def test_eq_normalizes_supported_value_types(value, expected):
    expr = F["x"]._eq(value)
    assert isinstance(expr, LeafExpr)
    assert expr.pred.op == Op.EQ
    assert expr.pred.value == expected


def test_in_accepts_tuple_and_normalizes_to_list():
    expr = F["x"].is_in((1, 2, 3))
    assert expr.pred.op == Op.IN
    assert expr.pred.value == [1, 2, 3]


def test_in_accepts_generator_and_normalizes_to_list():
    expr = F["x"].is_in(v for v in [1, 2])
    assert expr.pred.op == Op.IN
    assert expr.pred.value == [1, 2]


def test_in_list_of_enums_normalizes_elements():
    expr = F["color"].is_in((Color.RED, Color.BLUE))
    assert expr.pred.op == Op.IN
    assert expr.pred.value == ["red", "blue"]

def test_in_to_ast_dict_has_correct_cmp_and_value():
    expr = F["x"].is_in([1, 2])
    ast = expr.to_ast_dict()
    assert ast == {"op": "LEAF", "field": "x", "cmp": "IN", "value": [1, 2]}


def test_not_in_to_ast_dict_has_correct_cmp_and_value():
    expr = F["x"].not_in([1, 2])
    ast = expr.to_ast_dict()
    assert ast == {"op": "LEAF", "field": "x", "cmp": "NIN", "value": [1, 2]}

def test_and_operator_builds_logicexpr():
    a = F["a"] == 1
    b = F["b"] == 2
    expr = a & b
    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.AND
    assert expr.children == (a, b)


def test_or_operator_builds_logicexpr():
    a = F["a"] == 1
    b = F["b"] == 2
    expr = a | b
    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.OR
    assert expr.children == (a, b)

def test_parentheses_affect_precedence():
    a = F["a"] == 1
    b = F["b"] == 2
    c = F["c"] == 3

    expr = (a | b) & c  # should parse as: (a | b) & c

    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.AND

    lhs = expr.children[0]
    assert isinstance(lhs, LogicExpr)
    assert lhs.op == LogicOp.OR
    assert lhs.children == (a, b)

    assert expr.children[1] is c

def test_parentheses_leave_expr_unchanged():
    a = (F["a"] == 1)
    b = F["b"] == 2
    assert isinstance(a, LeafExpr)

    expr = (a & b)

    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.AND
    assert expr.children == (a, b)


def test_logicexpr_to_ast_dict():
    a = F["a"] == 1
    b = F["b"] == 2
    expr = and_(a, b)
    ast = expr.to_ast_dict()
    assert ast["op"] == "AND"
    assert ast["children"] == [a.to_ast_dict(), b.to_ast_dict()]


def test_and_flattens_nested_and():
    a = F["a"] == 1
    b = F["b"] == 2
    c = F["c"] == 3
    expr = and_(and_(a, b), c)
    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.AND
    assert expr.children == (a, b, c)


def test_or_flattens_nested_or():
    a = F["a"] == 1
    b = F["b"] == 2
    c = F["c"] == 3
    expr = or_(or_(a, b), c)
    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.OR
    assert expr.children == (a, b, c)

def test_and_operator_chaining_flattens():
    a = F["a"] == 1
    b = F["b"] == 2
    c = F["c"] == 3
    expr = (a & b) & c
    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.AND
    assert expr.children == (a, b, c)


def test_or_operator_chaining_flattens():
    a = F["a"] == 1
    b = F["b"] == 2
    c = F["c"] == 3
    expr = (a | b) | c
    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.OR
    assert expr.children == (a, b, c)


def test_python_operator_precedence_and_before_or():
    a = F["a"] == 1
    b = F["b"] == 2
    c = F["c"] == 3

    expr = a | b & c  # should parse as: a | (b & c)

    assert isinstance(expr, LogicExpr)
    assert expr.op == LogicOp.OR
    assert expr.children[0] is a

    rhs = expr.children[1]
    assert isinstance(rhs, LogicExpr)
    assert rhs.op == LogicOp.AND
    assert rhs.children == (b, c)


def test_and_requires_at_least_one_expr():
    with pytest.raises(ValueError):
        and_()  # type: ignore[misc]


def test_or_requires_at_least_one_expr():
    with pytest.raises(ValueError):
        or_()  # type: ignore[misc]


def test_and_requires_at_least_two_after_flattening():
    a = F["a"] == 1
    with pytest.raises(ValueError):
        and_(a)


def test_or_requires_at_least_two_after_flattening():
    a = F["a"] == 1
    with pytest.raises(ValueError):
        or_(a)


def test_logicexpr_post_init_rejects_lt2_children():
    a = F["a"] == 1
    with pytest.raises(ValueError):
        LogicExpr(op=LogicOp.AND, children=(a,))


def test_all_of_empty_raises():
    with pytest.raises(ValueError):
        all_of([])


def test_any_of_empty_raises():
    with pytest.raises(ValueError):
        any_of([])


def test_all_of_single_returns_same_object():
    a = F["a"] == 1
    out = all_of([a])
    assert out is a


def test_any_of_single_returns_same_object():
    a = F["a"] == 1
    out = any_of([a])
    assert out is a


def test_all_of_multiple_is_and():
    a = F["a"] == 1
    b = F["b"] == 2
    out = all_of([a, b])
    assert isinstance(out, LogicExpr)
    assert out.op == LogicOp.AND
    assert out.children == (a, b)


def test_any_of_multiple_is_or():
    a = F["a"] == 1
    b = F["b"] == 2
    out = any_of([a, b])
    assert isinstance(out, LogicExpr)
    assert out.op == LogicOp.OR
    assert out.children == (a, b)


def test_expr_cannot_be_used_in_boolean_context():
    a = F["a"] == 1
    with pytest.raises(TypeError):
        bool(a)

def test_logicexpr_cannot_be_used_in_boolean_context():
    a = F["a"] == 1
    b = F["b"] == 2
    expr = a & b
    with pytest.raises(TypeError):
        bool(expr)

def test_logicexpr_can_only_be_made_using_other_expr():
    a = F["a"] == 1
    with pytest.raises(TypeError):
        expr = a & ("not an expr" == 2)

