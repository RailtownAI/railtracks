import re
import pytest

from railtracks.rag.vector_store.utils import (
    uuid_str,
    normalize_vector,
    distance,
    stable_hash,
)

def test_uuid_str_format():
    s = uuid_str()
    assert re.fullmatch(r'[0-9a-f\-]{36}', s)
    assert len(s) == 36

def test_normalize_vector_nonzero():
    v = [3, 4]
    normed = normalize_vector(v)
    assert abs(sum(x**2 for x in normed) - 1) < 1e-8
    assert normed[0] == 0.6
    assert normed[1] == 0.8

def test_normalize_vector_zero():
    v = [0, 0, 0]
    assert normalize_vector(v) == [0, 0, 0]

def test_distance_l2():
    a = [1, 2, 3]
    b = [1, 3, 2]
    assert distance(a, b, "l2") == 2

def test_distance_dot():
    a = [1, 2]
    b = [3, 4]
    assert distance(a, b, "dot") == -(1*3 + 2*4)

def test_distance_cosine():
    a = [1, 0]
    b = [0, 1]
    assert distance(a, b, "cosine") == -0.0
    assert distance([3, 4], [3, 4], "cosine") == -1.0

def test_distance_bad_metric():
    with pytest.raises(ValueError):
        distance([1,2], [3,4], "foo")

def test_stable_hash():
    h = stable_hash("foo")
    assert h == stable_hash("foo")
    assert h != stable_hash("bar")
    assert len(h) == 64
    assert re.fullmatch(r'[0-9a-f]{64}', h)