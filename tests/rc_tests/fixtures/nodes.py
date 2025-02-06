from __future__ import annotations

import random
import time

from enum import Enum
from typing import List, Callable
from requestcompletion.nodes import Node, NodeFactory
from requestcompletion.exceptions import *


EMPHATIC_ERROR = "The Node has failed emphatically"

REGULAR_ERROR = "The Node has failed regularly"


class CapitalizeText(Node[str]):
    def __init__(self, data: str):
        super().__init__()
        self.data = data

    @classmethod
    def pretty_name(cls) -> str:
        return "Capitalize Text Node"

    def invoke(self) -> str:
        return self.data.capitalize()


class FatalErrorNode(Node[str]):
    def invoke(self):
        raise FatalException(
            self,
            detail=EMPHATIC_ERROR,
        )

    @classmethod
    def pretty_name(cls) -> str:
        return "Fatal Error Node"


class CompletionProtocolNode(Node[str]):
    def __init__(self, completion_protocol: str):
        super().__init__()
        self.completion_protocol = completion_protocol

    def invoke(self):
        raise CompletionException(
            self,
            detail=REGULAR_ERROR,
            completion_protocol=self.completion_protocol,
        )

    @classmethod
    def pretty_name(cls) -> str:
        return "Error Node"


class ScorchedEarthNode(Node[str]):
    def invoke(self):
        raise ResetException(
            self,
            detail=REGULAR_ERROR,
        )

    @classmethod
    def pretty_name(cls) -> str:
        return "Scorched Earth Node"


class UnknownErrorNode(Node):
    def invoke(
        self,
    ):
        raise Exception("Something went wrong")

    @classmethod
    def pretty_name(cls) -> str:
        return "Unknown Error Node"


class RNGNode(Node[float]):
    def invoke(
        self,
    ) -> float:
        return random.random()

    @classmethod
    def pretty_name(cls) -> str:
        return "RNG Node"


class CallNode(Node[List]):
    def __init__(
        self,
        number_of_calls: int,
        parallel_call_num: int,
        node_creator: Callable[[], Node],
    ):
        super().__init__()
        self.number_of_calls = number_of_calls
        self.parallel_call_num = parallel_call_num
        self.node_creator = node_creator

        self.data: List = []

    def invoke(self):
        for _ in range(self.number_of_calls):
            response = self.call_nodes(
                [NodeFactory(self.node_creator) for _ in range(self.parallel_call_num)]
            )

            self.data.extend([d.data for d in response])

        return self.data

    @classmethod
    def pretty_name(cls) -> str:
        return "Call Node"


class TimeoutNode(Node):
    def __init__(self, timeout: float):
        super().__init__()
        self.timeout = timeout

    def invoke(self) -> None:
        time.sleep(self.timeout)
        return None

    @classmethod
    def pretty_name(cls) -> str:
        return "Timeout Node"


class ActionType(Enum):
    RNG = "rng"
    FATAL = "fatal"
    COMPLETION_FAIL = "completion_fail"
    REGULAR_FAIL = "regular_fail"
    UNKNOWN = "unknown"
    CALL = "call"


class StreamingRNGNode(RNGNode):
    """
    A simple RNG that streams data when an output is collected according `cls.rng_template`
    """

    rng_template = "RNG collected {0}"

    def invoke(
        self,
    ) -> float:
        response = super().invoke()
        self.data_streamer(self.rng_template.format(response))
        # this sleep is important for testing
        # if the thing returns too fast, the streamer will kill before it is able to finish its process.
        # time.sleep(0.01)
        return response


class StreamingCallNode(CallNode):
    call_template_call = "Creating Call with type {0}"

    def invoke(self):
        for _ in range(self.number_of_calls):
            nodes = [
                NodeFactory(self.node_creator) for _ in range(self.parallel_call_num)
            ]
            for n in nodes:
                self.data_streamer(self.call_template_call.format(n.new_node))
            response = self.call_nodes(nodes)

            self.data.extend([d.data for d in response])

        return self.data


if __name__ == "__main__":
    sen = ScorchedEarthNode()
    from copy import deepcopy

    copy = deepcopy(sen)
    print(copy)
