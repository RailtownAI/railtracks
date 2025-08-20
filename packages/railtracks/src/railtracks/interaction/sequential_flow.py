from typing import Callable, List, ParamSpec, TypeVar

from ..nodes.nodes import Node
import railtracks as rt

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

class NodeBundle:
    def __init__(self, node : Callable[_P, Node[_TOutput]], gets: str, puts: str):
        self.node = node
        self.input = gets
        self.output = puts
    
class NodeLoop:
    def __init__(self, node_loop: List, until: NodeBundle, action: str, value: str):
        self.node_loop = node_loop
        self.until = until
        self.action = action
        self.value = value

class flow:
    def __init__(self):
        self.context_vars = {}

    def make(self, node: Callable[_P, Node[_TOutput]], gets: str, puts: str):
        return NodeBundle(node, gets, puts)
    
    def loop(self, *args : NodeBundle | NodeLoop, until : NodeBundle, action : str, value : str):
        """
        Creates a loop that will run the provided nodes until the specified node gets/puts a certain value.
        """
        return NodeLoop([nodes for nodes in args], until, action, value)
    
    def _loop(self, loop: NodeLoop):
        """
        Runs the loop with the provided nodes.
        """
        for node in loop.node_loop:
            if isinstance(node, NodeBundle):
                

    def run(self, prompt : str, *args : NodeBundle | NodeLoop):
        """ Runs the flow with the provided prompt and nodes."""

        with rt.Session():
            rt.context.put("prompt", prompt)
            self.context_vars["prompt"] = prompt

            for node in args:
                if isinstance(node, NodeBundle):
                    response = rt.call_sync(node.node, user_input=rt.context.get(node.input))
                    rt.context.put(node.output, response.text) #We will need to change whole file to deal with structured responses
                    self.context_vars[node.output] = response.text #Same here
                elif isinstance(node, NodeLoop):
                    for sub_node in node.node_loop:
    
    def get(self, key: str):
        """ Retrieves the output from the flow."""
        return self.context_vars[key]