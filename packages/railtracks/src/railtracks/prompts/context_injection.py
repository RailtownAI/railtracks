from __future__ import annotations

from typing import TYPE_CHECKING

from railtracks.prompts.prompt import inject_context

if TYPE_CHECKING:
    from pydantic import BaseModel

    from railtracks.llm.history import MessageHistory
    from railtracks.llm.tools.tool import Tool


class ContextInjectionPreMapper:
    """
    A pre-mapper that injects context variables into message history placeholders.

    Satisfies the GatewayPreMapper protocol so it can be passed directly to a
    ModelGateway(pre_mappers=[...]) once that interface is available (PR #1132).

    Injection is controlled at two levels:
    - Session level: ExecutorConfig(prompt_injection=False) disables it globally.
    - Message level: Message(inject_prompt=False) skips a specific message.
    """

    def __call__(
        self,
        messages: "MessageHistory",
        schema: "type[BaseModel] | None" = None,
        tools: "list[Tool] | None" = None,
    ) -> "tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]":
        return inject_context(messages), schema, tools
