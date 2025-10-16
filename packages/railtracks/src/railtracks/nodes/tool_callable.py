from typing_extensions import Self

from railtracks.llm import Tool


class ToolCallable:
    @classmethod
    def tool_info(cls) -> Tool:
        """
        A method used to provide information about the node in the form of a tool definition.
        This is commonly used with LLMs Tool Calling tooling.
        """
        # TODO: this should default to interfacing within the init method of the class
        raise NotImplementedError(
            "You must implement the tool_info method in your node"
        )

    @classmethod
    def prepare_tool(cls, **kwargs) -> Self:
        """
        This method creates a new instance of the node by unpacking the tool parameters.

        If you would like any custom behavior please override this method.
        """
        return cls(**kwargs)  # noqa
