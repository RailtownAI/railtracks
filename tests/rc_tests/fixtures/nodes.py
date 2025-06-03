from __future__ import annotations

import asyncio
import random

from enum import Enum
from typing import List, Callable
import requestcompletion as rc

EMPHATIC_ERROR = "The Node has failed emphatically"

REGULAR_ERROR = "The Node has failed regularly"


class CapitalizeText(rc.Node[str]):
    def __init__(self, data: str):
        super().__init__()
        self.data = data

    @classmethod
    def pretty_name(cls) -> str:
        return "Capitalize Text Node"

    def invoke(self) -> str:
        return self.data.capitalize()


class UnknownErrorNode(rc.Node):
    def invoke(
        self,
    ):
        raise Exception("Something went wrong")

    @classmethod
    def pretty_name(cls) -> str:
        return "Unknown Error Node"


class RNGNode(rc.Node[float]):
    def invoke(
        self,
    ) -> float:
        return random.random()

    @classmethod
    def pretty_name(cls) -> str:
        return "RNG Node"


class CallNode(rc.Node[List]):
    def __init__(
        self,
        number_of_calls: int,
        parallel_call_num: int,
        node_creator: Callable[[], rc.Node],
    ):
        super().__init__()
        self.number_of_calls = number_of_calls
        self.parallel_call_num = parallel_call_num
        self.node_creator = node_creator

        self.data: List = []

    def invoke(self):
        for _ in range(self.number_of_calls):
            contracts = [
                rc.call(self.node_creator) for _ in range(self.parallel_call_num)
            ]
            response = asyncio.gather(*contracts)

            self.data.extend([d for d in response])

        return self.data

    @classmethod
    def pretty_name(cls) -> str:
        return "Call Node"


class TimeoutNode(rc.Node):
    def __init__(self, timeout: float):
        super().__init__()
        self.timeout = timeout

    async def invoke(self) -> None:
        await asyncio.sleep(self.timeout)
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

    async def invoke(
        self,
    ) -> float:
        response = super().invoke()
        rc.stream(self.rng_template.format(response))
        # this sleep is important for testing
        # if the thing returns too fast, the streamer will kill before it is able to finish its process.
        # time.sleep(0.01)
        return response


class StreamingCallNode(CallNode):
    call_template_call = "Creating Call with type {0}"

    def invoke(self):
        for _ in range(self.number_of_calls):
            contracts = [
                rc.call(self.node_creator) for _ in range(self.parallel_call_num)
            ]
            response = asyncio.gather(*contracts)
            [rc.stream(r) for r in response]

            self.data.extend([d for d in response])

        return self.data
