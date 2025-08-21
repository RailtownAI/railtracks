import asyncio
from abc import ABC

from railtracks.exceptions import LLMError
from railtracks.interaction import call
from railtracks.llm import (
    AssistantMessage,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.llm.message import Role

from ._llm_base import StringOutputMixIn
from ._tool_call_base import OutputLessToolCallLLM
from .response import StringResponse


class ChatToolCallLLM(StringOutputMixIn, OutputLessToolCallLLM[StringResponse], ABC):
    chat_ui = None

    async def invoke(self):  # noqa: C901
        # If there's no last user message, we need to wait for user input
        if self.message_hist[-1].role != Role.user:
            msg = await self.chat_ui.wait_for_user_input()
            if msg == "EXIT":
                return self.return_output()
            self.message_hist.append(
                UserMessage(
                    msg,
                )
            )

        while True:
            current_tool_calls = len(
                [m for m in self.message_hist if isinstance(m, ToolMessage)]
            )
            allowed_tool_calls = (
                self.max_tool_calls - current_tool_calls
                if self.max_tool_calls is not None
                else None
            )
            if self.max_tool_calls is not None and allowed_tool_calls <= 0:
                await self._on_max_tool_calls_exceeded()
                break

            # collect the response from the model
            returned_mess = self.llm_model.chat_with_tools(
                self.message_hist, tools=self.tools()
            )

            if returned_mess.message.role == "assistant":
                # if the returned item is a list then it is a list of tool calls
                if isinstance(returned_mess.message.content, list):
                    assert all(
                        isinstance(x, ToolCall) for x in returned_mess.message.content
                    )

                    tool_calls = returned_mess.message.content
                    if (
                        allowed_tool_calls is not None
                        and len(tool_calls) > allowed_tool_calls
                    ):
                        tool_calls = tool_calls[:allowed_tool_calls]

                    # append the requested tool calls assistant message, once the tool calls have been verified and truncated (if needed)
                    self.message_hist.append(AssistantMessage(content=tool_calls))

                    contracts = []
                    for t_c in tool_calls:
                        contract = call(
                            self.create_node,
                            t_c.name,
                            t_c.arguments,
                        )
                        contracts.append(contract)

                    tool_responses = await asyncio.gather(
                        *contracts, return_exceptions=True
                    )
                    tool_responses = [
                        (
                            x
                            if not isinstance(x, Exception)
                            else f"There was an error running the tool: \n Exception message: {x} "
                        )
                        for x in tool_responses
                    ]
                    tool_ids = [x.identifier for x in tool_calls]
                    tool_names = [x.name for x in tool_calls]

                    for r_id, r_name, resp in zip(
                        tool_ids,
                        tool_names,
                        tool_responses,
                    ):
                        self.message_hist.append(
                            ToolMessage(
                                ToolResponse(
                                    identifier=r_id, result=str(resp), name=r_name
                                )
                            )
                        )

                        # Update the tools tab in the UI
                        success = not isinstance(resp, str) or not resp.startswith(
                            "There was an error running the tool:"
                        )
                        await self.chat_ui.update_tools(
                            tool_name=r_name,
                            tool_id=r_id,
                            arguments=next(
                                tc.arguments
                                for tc in tool_calls
                                if tc.identifier == r_id
                            ),
                            result=str(resp),
                            success=success,
                        )
                else:
                    assistant_message = returned_mess.message.content

                    self.message_hist.append(
                        AssistantMessage(content=assistant_message)
                    )
                    await self.chat_ui.send_message(assistant_message)

                    user_message = await self.chat_ui.wait_for_user_input()
                    if user_message == "EXIT":
                        break
                    self.message_hist.append(UserMessage(content=user_message))
            else:
                # the message is malformed from the model
                raise LLMError(
                    reason="ModelLLM returned an unexpected message type.",
                    message_history=self.message_hist,
                )

        return self.return_output()

    @classmethod
    def type(cls):
        return "Agent"
