from typing import Iterable, List

import railtracks as rt
from railtracks.llm import Parameter


class ToolManifest:
    """
    Creates a manifest for a tool, which includes its description and parameters.

    Args:
        tool_description (str): A description of the tool.
        tool_parameters (Iterable[Parameter] | None): An iterable of parameters for the tool. If None, there are no paramerters.
    """
    def __init__(
            self,
            description: str,
            parameters: Iterable[Parameter] | None = None,
    ):

        self.description = description
        self.parameters: List[Parameter] = list(parameters) if parameters is not None else []



