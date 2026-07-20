import asyncio
from unittest.mock import patch

import pytest
import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.exceptions.errors import LLMError
from railtracks.guardrails.core import (
    GuardrailBlockedError,
    GuardrailDecision,
    InputGuard,
    OutputGuard,
)
from railtracks.llm import AssistantMessage, MessageHistory, ToolCall, UserMessage
from railtracks.llm.response import MessageInfo, Response

import litellm
from jsonschema import validate
from railtracks.llm.retries.fixed import FixedRetry



# ---------------------------------------------------------------------------
# TestFunctionNodeMiddleware
# ---------------------------------------------------------------------------


class TestFunctionNodeMiddleware:
    """Middleware attached to function node boundaries (user args -> return value),
    across all three `rt.function_node` calling forms."""

    async def test_direct_call_form(self):
        log = []

        @rt.wrap_node
        async def tracer(call, *args, **kwargs):
            log.append("in")
            result = await call(*args, **kwargs)
            log.append("out")
            return result

        def add(x: int, y: int) -> int:
            return x + y

        node = rt.function_node(add, middleware=[tracer])
        result = await rt.Flow("direct_call", node).ainvoke(3, 4)

        assert result == 7
        assert log == ["in", "out"]

    async def test_bare_decorator_form_has_no_middleware(self):
        @rt.function_node
        def add(x: int, y: int) -> int:
            return x + y

        result = await rt.Flow("bare_decorator", add).ainvoke(3, 4)
        assert result == 7

    async def test_parametrized_decorator_form(self):
        log = []

        @rt.wrap_node
        async def tracer(call, *args, **kwargs):
            log.append("in")
            return await call(*args, **kwargs)

        @rt.function_node(middleware=[tracer], name="echo")
        def echo(text: str) -> str:
            return text

        result = await rt.Flow("parametrized_decorator", echo).ainvoke("hi")

        assert result == "hi"
        assert log == ["in"]

    async def test_list_of_functions_form_applies_same_middleware_to_each(self):
        log = []

        @rt.wrap_node
        async def tracer(call, *args, **kwargs):
            log.append(call.__name__ if hasattr(call, "__name__") else "call")
            return await call(*args, **kwargs)

        def add(x: int, y: int) -> int:
            return x + y

        def sub(x: int, y: int) -> int:
            return x - y

        add_node, sub_node = rt.function_node([add, sub], middleware=[tracer])

        add_result = await rt.Flow("list_add", add_node).ainvoke(3, 4)
        sub_result = await rt.Flow("list_sub", sub_node).ainvoke(10, 4)

        assert add_result == 7
        assert sub_result == 6
        assert len(log) == 2  # tracer fired once per node

    async def test_middleware_transforms_args_before_call(self):
        @rt.wrap_node
        async def uppercase_in(call, text):
            return await call(text.upper())

        @rt.function_node(middleware=[uppercase_in])
        def echo(text: str) -> str:
            return text

        result = await rt.Flow("test_echo", echo).ainvoke("hello")
        assert result == "HELLO"

    async def test_middleware_transforms_output_after_call(self):
        @rt.wrap_node
        async def double_out(call, *args, **kwargs):
            result = await call(*args, **kwargs)
            return result * 2

        @rt.function_node(middleware=[double_out])
        def add(x: int, y: int) -> int:
            return x + y

        result = await rt.Flow("test_add", add).ainvoke(3, 4)
        assert result == 14  # (3 + 4) * 2

    async def test_middleware_raising_prevents_the_call(self):
        @rt.wrap_node
        async def no_negatives(call, x, y):
            if x < 0 or y < 0:
                raise ValueError("Negative numbers not allowed")
            return await call(x, y)

        @rt.function_node(middleware=[no_negatives])
        def add(x: int, y: int) -> int:
            return x + y

        with pytest.raises(ValueError, match="Negative"):
            await rt.Flow("test_add_guardrail", add).ainvoke(-1, 5)

    async def test_middleware_retries_on_failure(self):
        attempt = {"count": 0}

        @rt.wrap_node
        async def retry_once(call, *args, **kwargs):
            try:
                return await call(*args, **kwargs)
            except ValueError:
                return await call(*args, **kwargs)

        @rt.function_node(middleware=[retry_once])
        async def flaky() -> str:
            attempt["count"] += 1
            if attempt["count"] < 2:
                raise ValueError("not ready")
            return "ok"

        result = await rt.Flow("test_flaky", flaky).ainvoke()

        assert result == "ok"
        assert attempt["count"] == 2

    async def test_middleware_short_circuits(self):
        @rt.wrap_node
        async def block(call, *args, **kwargs):
            return "blocked"

        @rt.function_node(middleware=[block])
        async def should_not_run() -> str:
            raise AssertionError("core should not be called")

        result = await rt.Flow("test_block", should_not_run).ainvoke()
        assert result == "blocked"

    async def test_multiple_middleware_outer_to_inner_order(self):
        log = []

        @rt.wrap_node
        async def first(call, *args, **kwargs):
            log.append("first_before")
            result = await call(*args, **kwargs)
            log.append("first_after")
            return result

        @rt.wrap_node
        async def second(call, *args, **kwargs):
            log.append("second_before")
            result = await call(*args, **kwargs)
            log.append("second_after")
            return result

        @rt.function_node(middleware=[first, second])
        def identity(x: int) -> int:
            log.append("core")
            return x

        result = await rt.Flow("test_wrapper_order", identity).ainvoke(0)

        assert result == 0
        assert log == [
            "first_before",
            "second_before",
            "core",
            "second_after",
            "first_after",
        ]


# ---------------------------------------------------------------------------
# TestAgentNodeMiddleware
# ---------------------------------------------------------------------------


class TestAgentNodeMiddleware:
    """Middleware at the agent node boundary (user_input -> StringResponse/StructuredResponse)."""

    async def test_node_level_middleware_fires_after_response(self, mock_llm):
        side_effects = {"called": False}

        @rt.wrap_node
        async def mark_called(call, *args, **kwargs):
            result = await call(*args, **kwargs)
            side_effects["called"] = True
            return result

        agent = rt.agent_node(
            name="ExitAgent",
            llm=mock_llm(custom_response="hello"),
            middleware=[mark_called],
        )

        result = await rt.Flow("ExitAgent", agent).ainvoke("hi")

        assert side_effects["called"]
        assert "hello" in result.content

    async def test_node_level_wrapper_wraps_whole_agent_invocation(self, mock_llm):
        call_count = {"n": 0}

        @rt.wrap_node
        async def count_calls(call, *args, **kwargs):
            call_count["n"] += 1
            return await call(*args, **kwargs)

        agent = rt.agent_node(
            name="CountedAgent",
            llm=mock_llm(custom_response="done"),
            middleware=[count_calls],
        )

        await rt.Flow("CountedAgent", agent).ainvoke("run once")

        assert call_count["n"] == 1

    async def test_node_level_middleware_blocks_before_llm_is_called(self, mock_llm):
        llm_called = {"value": False}

        def track_and_respond(messages):
            llm_called["value"] = True
            return Response(
                message=AssistantMessage("should not appear"),
                message_info=MessageInfo(model_name="m"),
            )

        model = mock_llm()
        model._chat = track_and_respond

        @rt.wrap_node
        async def block_all(call, *args, **kwargs):
            raise PermissionError("Access denied")

        agent = rt.agent_node(name="BlockedAgent", llm=model, middleware=[block_all])

        with pytest.raises(PermissionError, match="Access denied"):
            await rt.Flow("BlockedAgent", agent).ainvoke("attempt this")

        assert not llm_called["value"]

    async def test_structured_output_agent_with_node_level_middleware(self, mock_llm):
        class Answer(BaseModel):
            value: int = Field(description="The answer")

        captured = {}

        @rt.wrap_node
        async def capture_response(call, *args, **kwargs):
            result = await call(*args, **kwargs)
            captured["response"] = result
            return result

        agent = rt.agent_node(
            name="StructuredAgent",
            llm=mock_llm(custom_response='{"value": 42}'),
            output_schema=Answer,
            middleware=[capture_response],
        )

        result = await rt.Flow("StructuredAgent", agent).ainvoke("what is the answer?")

        assert result.structured.value == 42
        assert captured["response"] is result


# ---------------------------------------------------------------------------
# TestModelMiddleware
# ---------------------------------------------------------------------------


class TestModelMiddleware:
    """Middleware around each raw model call (messages/schema/tools -> Response)."""

    async def test_model_middleware_invoked_once_per_raw_model_call(self, mock_llm):
        invocations = {"n": 0}

        @rt.wrap_node
        async def count_model_calls(call, *args, **kwargs):
            invocations["n"] += 1
            return await call(*args, **kwargs)

        agent = rt.agent_node(
            name="CountedModel",
            llm=mock_llm(custom_response="reply"),
            model_middleware=[count_model_calls],
        )

        await rt.Flow("CountedModel", agent).ainvoke("hello")

        assert invocations["n"] == 1

    async def test_model_middleware_fires_once_per_tool_loop_iteration(self, mock_llm):
        """A tool-calling round trip means two raw model calls: one that requests the
        tool, one that produces the final reply -- model_middleware must fire for both."""
        invocations = {"n": 0}

        @rt.wrap_node
        async def count_model_calls(call, *args, **kwargs):
            invocations["n"] += 1
            return await call(*args, **kwargs)

        def double(n: int) -> int:
            """Doubles a number.
            Args:
                n (int): The number to double.
            Returns:
                int: The doubled number.
            """
            return n * 2

        llm = mock_llm(
            requested_tool_calls=[ToolCall(name="double", identifier="c1", arguments={"n": 5})]
        )
        agent = rt.agent_node(
            name="ToolLoopModel",
            llm=llm,
            tool_nodes=[rt.function_node(double)],
            model_middleware=[count_model_calls],
        )

        await rt.Flow("ToolLoopModel", agent).ainvoke("double 5")

        assert invocations["n"] == 2

    async def test_model_middleware_can_inspect_messages_before_call(self, mock_llm):
        seen_roles = []

        @rt.wrap_node
        async def capture_roles(call, messages, schema, tools):
            for m in messages:
                seen_roles.append(m.role)
            return await call(messages, schema, tools)

        agent = rt.agent_node(
            name="RoleCapture",
            llm=mock_llm(custom_response="ok"),
            system_message="You are a helper.",
            model_middleware=[capture_roles],
        )

        await rt.Flow("RoleCapture", agent).ainvoke("question")

        assert "system" in seen_roles
        assert "user" in seen_roles

    async def test_model_middleware_can_modify_messages_before_call(self, mock_llm):
        received_content = []

        @rt.wrap_node
        async def inject_header(call, messages, schema, tools):
            new_messages = MessageHistory(list(messages))
            new_messages.insert(0, UserMessage("[INJECTED]"))
            return await call(new_messages, schema, tools)

        @rt.wrap_node
        async def capture_first_message(call, messages, schema, tools):
            received_content.append(messages[0].content)
            return await call(messages, schema, tools)

        agent = rt.agent_node(
            name="InjectionAgent",
            llm=mock_llm(custom_response="ok"),
            model_middleware=[inject_header, capture_first_message],
        )

        await rt.Flow("InjectionAgent", agent).ainvoke("actual question")

        assert received_content[0] == "[INJECTED]"

    async def test_model_middleware_wrapper_can_retry_on_llm_error(self, mock_llm):
        """model_middleware wraps _core_llm_call directly, so the wrapper sees the raw
        exception -- LLMError wrapping happens one layer above in llm_invoke_factory,
        after the middleware stack unwinds."""

        attempts = {"n": 0}

        @rt.wrap_node
        async def retry_llm(call, *args, **kwargs):
            for _ in range(3):
                try:
                    return await call(*args, **kwargs)
                except Exception:
                    attempts["n"] += 1
            raise LLMError(reason="exhausted", message_history=args[0])

        llm = mock_llm(
            custom_response="success",
            errors=[lambda: Exception("transient network error")],
        )

        agent = rt.agent_node(
            name="RetryAgent",
            llm=llm,
            model_middleware=[retry_llm],
        )

        result = await rt.Flow("RetryAgent", agent).ainvoke("try this")

        assert "success" in result.content
        assert attempts["n"] == 1

    async def test_model_middleware_independent_per_agent_node(self, mock_llm):
        """Each agent node gets its own copy of model_middleware; middleware from one
        node never fires for another."""
        gate_a_calls = {"n": 0}
        gate_b_calls = {"n": 0}

        @rt.wrap_node
        async def mw_a(call, *args, **kwargs):
            gate_a_calls["n"] += 1
            return await call(*args, **kwargs)

        @rt.wrap_node
        async def mw_b(call, *args, **kwargs):
            gate_b_calls["n"] += 1
            return await call(*args, **kwargs)

        agent_a = rt.agent_node(
            "AgentA", llm=mock_llm(custom_response="a"), model_middleware=[mw_a]
        )
        agent_b = rt.agent_node(
            "AgentB", llm=mock_llm(custom_response="b"), model_middleware=[mw_b]
        )

        await rt.Flow("AgentA", agent_a).ainvoke("hello")
        await rt.Flow("AgentB", agent_b).ainvoke("hello")

        assert gate_a_calls["n"] == 1
        assert gate_b_calls["n"] == 1


# ---------------------------------------------------------------------------
# TestContextInjection
# ---------------------------------------------------------------------------


class TestContextInjection:
    """Context injection: rt.context values substituted into {placeholder} templates."""

    async def test_context_variable_injected_into_system_message(self, mock_llm):
        injected_system_content = []

        @rt.wrap_node
        async def capture_system(call, messages, schema, tools):
            for m in messages:
                if m.role == "system":
                    injected_system_content.append(m.content)
            return await call(messages, schema, tools)

        agent = rt.agent_node(
            name="TemplateAgent",
            llm=mock_llm(custom_response="done"),
            system_message="You assist {username}.",
            model_middleware=[capture_system],
        )

        await rt.Flow("TemplateAgent", agent, context={"username": "Alice"}).ainvoke(
            "help me"
        )

        assert any("Alice" in c for c in injected_system_content)

    async def test_context_injection_disabled_when_flag_is_false(self, mock_llm):
        injected_system_content = []

        @rt.wrap_node
        async def capture_system(call, messages, schema, tools):
            for m in messages:
                if m.role == "system":
                    injected_system_content.append(m.content)
            return await call(messages, schema, tools)

        agent = rt.agent_node(
            name="NoInjectionAgent",
            llm=mock_llm(custom_response="done"),
            system_message="You assist {username}.",
            model_middleware=[capture_system],
            context_injection=False,
        )

        await rt.Flow("NoInjectionAgent", agent, context={"username": "Alice"}).ainvoke(
            "help me"
        )

        assert all("{username}" in c for c in injected_system_content)


# ---------------------------------------------------------------------------
# TestGuardrailsEndToEnd
# ---------------------------------------------------------------------------


class TestGuardrailsEndToEnd:
    """Guardrails wired as plain entries in `agent_node(model_middleware=[...])`."""

    async def test_input_block_prevents_llm_call(self, mock_llm):
        llm_called = {"value": False}

        def track_and_respond(messages):
            llm_called["value"] = True
            return Response(
                message=AssistantMessage("leaked"), message_info=MessageInfo(model_name="m")
            )

        model = mock_llm()
        model._chat = track_and_respond

        class BlockAllInput(InputGuard):
            def __call__(self, event):
                return GuardrailDecision.block(reason="blocked input")

        agent = rt.agent_node(
            "GuardedInputAgent", llm=model, model_middleware=[BlockAllInput()]
        )

        with pytest.raises(GuardrailBlockedError):
            await rt.Flow("GuardedInputAgent", agent).ainvoke("attempt this")

        assert not llm_called["value"]

    async def test_output_block_on_terminal_response(self, mock_llm):
        class BlockAllOutput(OutputGuard):
            def __call__(self, event):
                return GuardrailDecision.block(reason="blocked output")

        agent = rt.agent_node(
            "GuardedOutputAgent",
            llm=mock_llm(custom_response="secret data"),
            model_middleware=[BlockAllOutput()],
        )

        with pytest.raises(GuardrailBlockedError):
            await rt.Flow("GuardedOutputAgent", agent).ainvoke("hi")

    async def test_output_guard_fires_only_on_final_reply(self, mock_llm):
        """OutputGuard is plain model_middleware and wraps every raw model call inside
        the tool-calling loop, but intermediate tool-call turns pass through unguarded —
        output rails fire only on the final content reply."""
        fired = {"n": 0}

        class CountingAllowOutput(OutputGuard):
            def __call__(self, event):
                fired["n"] += 1
                return GuardrailDecision.allow(reason="ok")

        def increment(n: int) -> int:
            """Increments a number.
            Args:
                n (int): The number.
            Returns:
                int: n + 1.
            """
            return n + 1

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="increment", identifier="id1", arguments={"n": 1})
            ]
        )
        agent = rt.agent_node(
            "GuardedToolAgent",
            llm=llm,
            tool_nodes=[rt.function_node(increment)],
            model_middleware=[CountingAllowOutput()],
        )

        result = await rt.Flow("GuardedToolAgent", agent).ainvoke("increment 1")

        # The intermediate tool-call turn is skipped; only the final reply is guarded.
        assert fired["n"] == 1
        assert "2" in result.content

    async def test_guardrail_block_is_not_wrapped_as_llmerror(self, mock_llm):
        """GuardrailBlockedError is a NodeInvocationError; llm_invoke_factory
        deliberately re-raises it as-is instead of masking it as a generic LLMError."""

        class BlockAllInput(InputGuard):
            def __call__(self, event):
                return GuardrailDecision.block(reason="blocked")

        agent = rt.agent_node(
            "GuardedAgent",
            llm=mock_llm(custom_response="hi"),
            model_middleware=[BlockAllInput()],
        )

        with pytest.raises(GuardrailBlockedError) as exc:
            await rt.Flow("GuardedAgent", agent).ainvoke("hi")
        assert not isinstance(exc.value, LLMError)

    async def test_node_level_middleware_sees_guardrail_block_uncaught(self, mock_llm):
        seen = {"exc_type": None}

        @rt.wrap_node
        async def observe(call, *args, **kwargs):
            try:
                return await call(*args, **kwargs)
            except Exception as e:
                seen["exc_type"] = type(e)
                raise

        class BlockAllInput(InputGuard):
            def __call__(self, event):
                return GuardrailDecision.block(reason="blocked")

        agent = rt.agent_node(
            "ObservedGuardedAgent",
            llm=mock_llm(custom_response="hi"),
            middleware=[observe],
            model_middleware=[BlockAllInput()],
        )

        with pytest.raises(GuardrailBlockedError):
            await rt.Flow("ObservedGuardedAgent", agent).ainvoke("hi")

        assert seen["exc_type"] is GuardrailBlockedError


# ---------------------------------------------------------------------------
# TestToolCallingWithPrepareArgs
# ---------------------------------------------------------------------------


class TestToolCallingWithPrepareArgs:
    """End-to-end tool calling via the NodeBuilder path (verifies the prepare_args fix)."""

    async def test_function_node_tool_called_with_correct_args(self, mock_llm):
        received = {}

        def double(n: int) -> int:
            """Doubles a number.
            Args:
                n (int): The number to double.
            Returns:
                int: The doubled number.
            """
            received["n"] = n
            return n * 2

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="double", identifier="call_001", arguments={"n": 5})
            ]
        )
        agent = rt.agent_node(
            name="DoubleAgent", llm=llm, tool_nodes=[rt.function_node(double)]
        )

        result = await rt.Flow("DoubleAgent", agent).ainvoke("double 5")

        assert received.get("n") == 5
        assert "10" in result.content

    async def test_multiple_parallel_tool_calls(self, mock_llm):
        calls_made = []

        def tag(label: str) -> str:
            """Tags a call.
            Args:
                label (str): The tag label.
            Returns:
                str: The label.
            """
            calls_made.append(label)
            return label

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="tag", identifier="id_a", arguments={"label": "alpha"}),
                ToolCall(name="tag", identifier="id_b", arguments={"label": "beta"}),
            ]
        )
        agent = rt.agent_node(name="MultiToolAgent", llm=llm, tool_nodes=[rt.function_node(tag)])

        await rt.Flow("MultiToolAgent", agent).ainvoke("tag alpha and beta")

        assert sorted(calls_made) == ["alpha", "beta"]

    async def test_tool_exception_surfaced_to_llm_as_string(self, mock_llm):
        def always_fails(x: int) -> int:
            """Always raises.
            Args:
                x (int): Input.
            Returns:
                int: Never returns.
            """
            raise RuntimeError("tool exploded")

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="always_fails", identifier="id_err", arguments={"x": 1})
            ]
        )
        agent = rt.agent_node(
            name="ErrorToolAgent", llm=llm, tool_nodes=[rt.function_node(always_fails)]
        )

        result = await rt.Flow("ErrorToolAgent", agent).ainvoke("call always_fails")

        # The error is surfaced to the LLM as a tool message string, not raised.
        assert result is not None

    async def test_function_node_tool_with_middleware_executes_middleware(self, mock_llm):
        fired = {"value": False}

        @rt.wrap_node
        async def mark_fired(call, *args, **kwargs):
            fired["value"] = True
            return await call(*args, **kwargs)

        def increment(n: int) -> int:
            """Increments a number.
            Args:
                n (int): The number.
            Returns:
                int: n + 1.
            """
            return n + 1

        tool = rt.function_node(increment, middleware=[mark_fired])

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="increment", identifier="id_inc", arguments={"n": 9})
            ]
        )
        agent = rt.agent_node(name="ToolWithMiddlewareAgent", llm=llm, tool_nodes=[tool])

        result = await rt.Flow("ToolWithMiddlewareAgent", agent).ainvoke("increment 9")

        assert fired["value"]
        assert "10" in result.content


# ---------------------------------------------------------------------------
# TestCoupleAndComposition
# ---------------------------------------------------------------------------


class TestCoupleAndComposition:
    """`rt.couple` post-hoc attachment, and multi-level composition of every
    injection mechanism on a single agent."""

    async def test_couple_attaches_middleware_after_build(self, mock_llm):
        log = []

        @rt.wrap_node
        async def tracer(call, *args, **kwargs):
            log.append("in")
            result = await call(*args, **kwargs)
            log.append("out")
            return result

        agent = rt.agent_node("CoupledAgent", llm=mock_llm(custom_response="ok"))
        agent = rt.couple(agent, middleware=[tracer])

        result = await rt.Flow("CoupledAgent", agent).ainvoke("hi")

        assert "ok" in result.content
        assert log == ["in", "out"]


    async def test_full_stack_composition_order(self, mock_llm):
        """Node-level middleware + model_middleware + guardrails + a post-hoc couple()
        all compose in the actual documented append order. Guardrails are ordinary
        model_middleware entries with no automatic slot: reproducing the classic
        "input guard closest to the model, output guard has the final say" shape now
        requires the caller to order the model_middleware list that way explicitly."""
        trace = []

        @rt.wrap_node
        async def node_a(call, *args, **kwargs):
            trace.append("node_a-in")
            result = await call(*args, **kwargs)
            trace.append("node_a-out")
            return result

        @rt.wrap_node
        async def node_c(call, *args, **kwargs):
            trace.append("node_c-in")
            result = await call(*args, **kwargs)
            trace.append("node_c-out")
            return result

        @rt.wrap_node
        async def model_b(call, *args, **kwargs):
            trace.append("model_b-in")
            result = await call(*args, **kwargs)
            trace.append("model_b-out")
            return result

        class TraceInputGuard(InputGuard):
            def __call__(self, event):
                trace.append("guardrail_input")
                return GuardrailDecision.allow(reason="ok")

        class TraceOutputGuard(OutputGuard):
            def __call__(self, event):
                trace.append("guardrail_output")
                return GuardrailDecision.allow(reason="ok")

        agent = rt.agent_node(
            "FullStackAgent",
            llm=mock_llm(custom_response="hi"),
            middleware=[node_a],
            model_middleware=[TraceOutputGuard(), model_b, TraceInputGuard()],
        )
        agent = rt.couple(agent, middleware=[node_c])

        await rt.Flow("FullStackAgent", agent).ainvoke("hello")

        assert (
            trace.index("node_a-in")
            < trace.index("node_c-in")
            < trace.index("node_c-out")
            < trace.index("node_a-out")
        )

        assert (
            trace.index("model_b-in")
            < trace.index("guardrail_input")
            < trace.index("model_b-out")
            < trace.index("guardrail_output")
        )


# ---------------------------------------------------------------------------
# TestMiddlewareIsolation
# ---------------------------------------------------------------------------


class TestMiddlewareIsolation:
    """Isolation guarantees: sharing a bare middleware list across nodes is safe."""

    async def test_shared_node_level_middleware_list_not_mutated(self, mock_llm):
        shared = []

        node_a = rt.agent_node("IsoA", llm=mock_llm(custom_response="a"), middleware=shared)
        node_b = rt.agent_node("IsoB", llm=mock_llm(custom_response="b"), middleware=shared)

        assert node_a._user_middleware is not node_b._user_middleware
        assert shared == []

    def test_node_instance_middleware_chain_independent_from_class(self, mock_llm):
        agent_cls = rt.agent_node("InstanceIso", llm=mock_llm())
        instance_a = agent_cls()
        instance_b = agent_cls()

        assert instance_a.middleware is not instance_b.middleware

    async def test_building_same_agent_repeatedly_does_not_accumulate(self, mock_llm):
        calls = {"n": 0}

        @rt.wrap_node
        async def counting(call, *args, **kwargs):
            calls["n"] += 1
            return await call(*args, **kwargs)

        shared = [counting]

        for _ in range(3):
            agent = rt.agent_node(
                "RepeatBuild", llm=mock_llm(custom_response="ok"), model_middleware=shared
            )
            await rt.Flow("RepeatBuild", agent).ainvoke("hi")

        assert calls["n"] == 3  # fires once per call, not accumulating across builds
        assert shared == [counting]  # the original list is untouched


# ---------------------------------------------------------------------------
# TestConcurrencyAndRetryInterplay
# ---------------------------------------------------------------------------


class TestConcurrencyAndRetryInterplay:
    async def test_concurrent_invocations_do_not_leak_state(self):
        order = []

        @rt.wrap_node
        async def tracer(call, tag):
            order.append(f"start-{tag}")
            result = await call(tag)
            order.append(f"end-{tag}")
            return result

        @rt.function_node(middleware=[tracer])
        async def slow_identity(tag: int) -> int:
            await asyncio.sleep(0.01 if tag == 0 else 0)
            return tag

        with rt.Session():
            results = await asyncio.gather(
                rt.call(slow_identity, 0),
                rt.call(slow_identity, 1),
            )

        assert sorted(results) == [0, 1]
        assert order.count("start-0") == 1
        assert order.count("end-0") == 1
        assert order.count("start-1") == 1
        assert order.count("end-1") == 1

    async def test_middleware_retry_and_builtin_retry_approach_do_not_conflict(
        self, mock_llm
    ):
        """A model_middleware retry wrapper and the built-in retry_approach operate at
        different layers -- retry_approach resolves entirely inside the single raw
        model call that model_middleware wraps, so they don't double up."""
       

        def rate_limited():
            return litellm.exceptions.RateLimitError(
                message="rate limited", llm_provider="mock", model="MockLLM"
            )

        middleware_attempts = {"n": 0}

        @rt.wrap_node
        async def count_attempts(call, *args, **kwargs):
            middleware_attempts["n"] += 1
            return await call(*args, **kwargs)

        llm = mock_llm(
            custom_response="final answer",
            errors=[rate_limited, rate_limited],
            retry_approach=FixedRetry(max_tries=5, delay=0.0),
        )
        agent = rt.agent_node(
            name="RetryInterplayAgent", llm=llm, model_middleware=[count_attempts]
        )

        with patch("railtracks.llm.retries.base.time.sleep"):
            result = await rt.Flow("RetryInterplayAgent", agent).ainvoke("hi")

        assert result.content == "final answer"
        assert middleware_attempts["n"] == 1


# ---------------------------------------------------------------------------
# TestSessionPersistence
# ---------------------------------------------------------------------------


class TestSessionPersistence:
    async def test_middleware_attached_node_serializes_cleanly(
        self, mock_llm, json_state_schema
    ):
       

        @rt.wrap_node
        async def tracer(call, *args, **kwargs):
            return await call(*args, **kwargs)

        agent = rt.agent_node(
            "PersistAgent", llm=mock_llm(custom_response="ok"), middleware=[tracer]
        )

        with rt.Session() as session:
            await rt.call(agent, user_input="hi")

        validate(session.payload(), json_state_schema)
