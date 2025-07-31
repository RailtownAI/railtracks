from collections import namedtuple
from typing import Dict, List, Tuple

from .node import LinkedNode, NodeForest
from .request import RequestForest, RequestTemplate

NodeRequestForestTuple = namedtuple(
    "NodeRequestForestTuple", ["node_forest", "request_forest"]
)


def create_sub_state_info(
    node_heap: Dict[str, LinkedNode],
    request_heap: Dict[str, RequestTemplate],
    parent_ids: str | List[str],
) -> Tuple[NodeForest, RequestForest]:
    """
    Creates a subset of the original heaps to include only the nodes and requests.

    The parent_ids will identify how the filtering should occur.
    - If a single ID is provided, it will be used as the root to find all downstream requests.
    - If a list of IDs is provided, it will find all requests downstream of each ID in the list.
    - If you provide multiple IDs on the same chain the behavior is undetermined.
    """
    valid_requests = {}
    node_ids = []
    for parent_id in parent_ids if isinstance(parent_ids, list) else [parent_ids]:
        source_id = request_heap[parent_id].sink_id
        requests_to_add = RequestTemplate.all_downstream(
            request_heap.values(), source_id
        ) + [request_heap[parent_id]]
        for r in requests_to_add:
            assert r.identifier not in valid_requests, (
                "There should not be any duplicate entries"
            )
            assert r.sink_id not in node_ids, (
                "There should not be any duplicate node IDs"
            )
            valid_requests[r.identifier] = r
            node_ids.append(r.sink_id)

    r_f = RequestForest(request_heap=valid_requests)

    n_f = NodeForest(
        node_heap={nid: node_heap[nid] for nid in node_ids if nid in node_heap}
    )

    return NodeRequestForestTuple(node_forest=n_f, request_forest=r_f)
