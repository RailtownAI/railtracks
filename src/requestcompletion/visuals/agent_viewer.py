from pyvis.network import Network

from typing import List

from ..utils.profiling import Stamp

from ..state.node import (
    LinkedNode,
    NodeForest,
)
from ..state.request import (
    RequestTemplate,
    RequestForest,
)


class AgentViewer:
    def __init__(
        self, stamps: List[Stamp], request_heap: RequestForest, node_heap: NodeForest
    ):
        """
        Creates a new instance of a `AgentViewer` object.

        Args:
            stamps (Stamp): all stamps from an executed run
            request_heap (RequestForest): the requests from an executed run
            node_heap (NodeForest):  the node heap from an executed run
        """
        self.stamps = stamps
        self.request_heap = request_heap
        self.node_heap = node_heap

    def view_all_steps(self):
        for stamp in self.stamps:
            print(f"Step: {stamp.step}: {stamp.identifier}")
        pass

    def view_at_step(self, step: int):
        # TODO: finish this
        raise NotImplementedError()

    def view_full_system_review(self):
        # TODO: finish this
        raise NotImplementedError()

    def _type_to_color(self, type: str):
        color_map = {
            "DirectorNode": "lightblue",
            "TerminalNode": "lightcoral",
            "Start": "springgreen",
        }
        return color_map.get(type, "gray")

    def _get_linkednode_info(self, linkednode: LinkedNode):
        name = linkednode.node.pretty_name()
        node_type = linkednode.node.__class__.__bases__[
            0
        ].__name__  # __bases__[0].__name__
        node_id = linkednode.node.uuid

        timelapse = f"{linkednode.stamp.step}: {linkednode.stamp.identifier}\n"
        parent = linkednode.parent

        while parent:
            linkednode = parent
            timelapse = (
                f"{linkednode.stamp.step}: {linkednode.stamp.identifier}\n" + timelapse
            )
            parent = linkednode.parent

        info = f"""{node_type}: {node_id}
                     {timelapse}"""

        return name, node_type, info, node_id

    def _get_edge_info(self, request_temp: RequestTemplate):
        output = f"""Request Output:
                    {request_temp.output}"""
        return output

    def display_node_link(self, linkednode_id: str):
        """
        Display a linkednode's steps for debugging
        Args:
            linkednode_id (str): uuid for the given node
        """

        linkednode = self.node_heap.heap()[linkednode_id]

        net = Network()

        linked_steps = []
        # Construct the chain
        while linkednode:
            node = (linkednode.stamp.step, linkednode.stamp.identifier)
            linked_steps.insert(0, node)
            linkednode = linkednode.parent

        curr = linked_steps.pop(0)
        net.add_node(f"Step: {curr[0]}", title=curr[1])
        while linked_steps:
            prev = curr
            curr = linked_steps.pop(0)
            net.add_node(f"Step: {curr[0]}", title=curr[1])
            net.add_edge(f"Step: {prev[0]}", f"Step: {curr[0]}")

        net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=200)
        title = f"Inspecting Node: {linkednode_id}"
        net_options = f"""
            var options = {{
                "title": "<h1 style='text-align:center;'>{title}</h1>"
            }}
            """
        net.set_options(net_options)
        net.show("interactive_node_link.html")

    def display_graph(self):
        """
        Constructs an interactive graph by creating an html file

        """
        SHAPE = "ellipse"
        FONT = {"size": 15, "align": "center"}
        SIZE = 30

        graph = RequestForest.generate_graph(self.request_heap.heap())

        net = Network()

        for source, connection_list in graph.items():
            for sink, req_id in connection_list:
                if not source:
                    src_name = "START"
                    src_type = "Start"
                    src_info = "Starting point for Agentic Flow"
                    src_id = "STRT"
                else:
                    src_name, src_type, src_info, src_id = self._get_linkednode_info(
                        self.node_heap[source]
                    )

                des_name, des_type, des_info, des_id = self._get_linkednode_info(
                    self.node_heap[sink]
                )

                net.add_node(
                    src_id,
                    label=src_name,
                    color=self._type_to_color(src_type),
                    shape=SHAPE,
                    font=FONT,
                    title=src_info,
                    size=SIZE,
                )
                net.add_node(
                    des_id,
                    label=des_name,
                    color=self._type_to_color(des_type),
                    shape=SHAPE,
                    font=FONT,
                    title=des_info,
                    size=SIZE,
                )

                net.add_edge(
                    src_id,
                    des_id,
                    label=req_id[:8],
                    title=self._get_edge_info(self.request_heap[req_id]),
                )

        net.force_atlas_2based(gravity=-100, central_gravity=0.001, spring_length=200)

        net.show("interactive_graph.html")
