from typing import Iterable, List

from railtracks.llm import Parameter


class ToolManifest:
    """
    Creates a manifest for a tool, which includes its description and parameters.

    Args:
        description (str): A description of the tool.
        parameters (Iterable[Parameter] | None): An iterable of parameters for the tool. If None, there are no paramerters.
    """

    def __init__(
        self,
        description: str,
        parameters: Iterable[Parameter] | None = None,
    ):
        self.description = description
        self.parameters: List[Parameter] = (
            list(parameters) if parameters is not None else []
        )
