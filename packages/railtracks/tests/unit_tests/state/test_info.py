import pytest
from unittest.mock import MagicMock, patch

from railtracks.state.info import ExecutionInfo

# ================= START ExecutionInfo: Fixtures and helpers ============

@pytest.fixture
def empty_request_forest():
    rf = MagicMock()
    rf.answer = None
    rf.insertion_request = []
    rf.__contains__.side_effect = lambda k: False
    rf.heap.return_value = []
    rf.to_edges.return_value = []
    return rf

@pytest.fixture
def empty_node_forest():
    nf = MagicMock()
    nf.heap.return_value = []
    nf.to_vertices.return_value = []
    return nf

@pytest.fixture
def empty_stamper():
    sm = MagicMock()
    sm._step = 0
    sm.all_stamps = []
    return sm

@pytest.fixture
def empty_info(empty_request_forest, empty_node_forest, empty_stamper):
    return ExecutionInfo(
        request_forest=empty_request_forest,
        node_forest=empty_node_forest,
        stamper=empty_stamper,
    )

def confirm_empty(info: ExecutionInfo):
    assert len(info.request_forest.heap()) == 0
    assert len(info.node_forest.heap()) == 0
    assert info.stamper._step == 0
    assert info.all_stamps == []
    assert info.answer is None
    assert info.insertion_requests == []
    assert info._get_info() == info
    with pytest.raises(ValueError):
        info._get_info(ids=["Not an id"])

# ================ END ExecutionInfo: Fixtures and helpers ===============

# ================= START ExecutionInfo: creation and defaults ============

def test_empty_starter():
    # Uses the true classes but everything's empty
    with patch("railtracks.state.info.RequestForest", return_value=MagicMock(
            answer=None, insertion_request=[], __contains__=lambda self, x: False, heap=lambda: [], to_edges=lambda: [])), \
         patch("railtracks.state.info.NodeForest", return_value=MagicMock(heap=lambda: [], to_vertices=lambda: [])), \
         patch("railtracks.state.info.StampManager", return_value=MagicMock(_step=0, all_stamps=[])):
        info = ExecutionInfo.create_new()
        confirm_empty(info)

def test_default():
    with patch("railtracks.state.info.RequestForest", return_value=MagicMock(
            answer=None, insertion_request=[], __contains__=lambda self, x: False, heap=lambda: [], to_edges=lambda: [])), \
         patch("railtracks.state.info.NodeForest", return_value=MagicMock(heap=lambda: [], to_vertices=lambda: [])), \
         patch("railtracks.state.info.StampManager", return_value=MagicMock(_step=0, all_stamps=[])):
        info = ExecutionInfo.default()
        confirm_empty(info)

# ================ END ExecutionInfo: creation and defaults ===============

# ================= START ExecutionInfo: property access ============

def test_properties_are_forwarded(empty_info, empty_stamper, empty_request_forest):
    # answer
    assert empty_info.answer is empty_request_forest.answer
    # all_stamps
    assert empty_info.all_stamps is empty_stamper.all_stamps
    # insertion_requests
    assert empty_info.insertion_requests is empty_request_forest.insertion_request

# ================ END ExecutionInfo: property access ===============

# ================= START ExecutionInfo: get_info logic ============

def test_get_info_no_ids_returns_self(empty_info):
    assert empty_info._get_info() is empty_info

def test_get_info_with_string_id_valid(monkeypatch, empty_info):
    # Simulate presence of id in request_forest
    id_ = "id1"
    empty_info.request_forest.__contains__.side_effect = lambda key: key == id_
    # Patch create_sub_state_info to return new minimal forests
    mock_new_rf = MagicMock()
    mock_new_nf = MagicMock()
    with patch("railtracks.state.info.create_sub_state_info", return_value=(mock_new_nf, mock_new_rf)):
        result = empty_info._get_info(ids=id_)
    assert isinstance(result, ExecutionInfo)
    assert result.node_forest is mock_new_nf
    assert result.request_forest is mock_new_rf
    assert result.stamper is empty_info.stamper

def test_get_info_with_list_id_valid(monkeypatch, empty_info):
    # Simulate presence of multiple ids
    ids = ["id1", "id2"]
    empty_info.request_forest.__contains__.side_effect = lambda key: key in ids
    with patch("railtracks.state.info.create_sub_state_info", return_value=(MagicMock(), MagicMock())):
        result = empty_info._get_info(ids=ids)
    # instance, and property propagation as above
    assert isinstance(result, ExecutionInfo)

def test_get_info_raises_value_error_on_bad_id(empty_info):
    empty_info.request_forest.__contains__.side_effect = lambda key: False
    with pytest.raises(ValueError):
        empty_info._get_info(ids="missing_id")

# ================ END ExecutionInfo: get_info logic ===============

# ================= START ExecutionInfo: graph methods ============

def test_to_graph_returns_vertices_and_edges(empty_info):
    # Set up mock return values
    vertices = [MagicMock(), MagicMock()]
    edges = [MagicMock()]
    empty_info.node_forest.to_vertices.return_value = vertices
    empty_info.request_forest.to_edges.return_value = edges
    v, e = empty_info._to_graph()
    assert v == vertices
    assert e == edges

def test_graph_serialization_serializes_json(empty_info):
    # nodes, edges, steps
    verts = [{"identifier": "n1"}, {"identifier": "n2"}]
    edgs = [{"source": None, "target": "n2"}]
    steps = [{"step": 0, "time": 0.0, "identifier": "x"}]
    empty_info.node_forest.to_vertices.return_value = verts
    empty_info.request_forest.to_edges.return_value = edgs
    empty_info.stamper.all_stamps = steps
    # patch RTJSONEncoder to just call default json
    with patch("railtracks.state.info.RTJSONEncoder", None):
        json_str = empty_info.graph_serialization()
        # quit test via presence of keywords (structure)
        assert json_str == []

# ================ END ExecutionInfo: graph methods ===============