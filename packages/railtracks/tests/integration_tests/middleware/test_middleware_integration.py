"""
Integration tests for the unified middleware system.

Covers:
  - Function node: entry/exit gateways, wrappers, ordering, guardrails
  - Agent node: node-level middleware (around the user_input → response boundary)
  - Model middleware: entry/exit gateways and wrappers around each raw model call
  - MiddlewareSet mechanics: fresh-copy isolation, gateway.args(), coerce()
  - Context injection via rt.context prompt templates
  - ModelSource factory form (model resolved fresh per call)
  - Tool calling with prepare_args (end-to-end verify of the prepare_tool→prepare_args fix)
"""

import asyncio

import pytest
import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.llm import ToolCall
from railtracks.middleware import MiddlewareSet


# ---------------------------------------------------------------------------
# TestFunctionNodeMiddleware
# ---------------------------------------------------------------------------


class TestFunctionNodeMiddleware:
    """Middleware attached to function node boundaries (user args → return value)."""

    @pytest.mark.asyncio
    async def test_entry_gateway_transforms_args(self):
        """Entry gateway can rewrite positional args before the function runs."""

        @rt.gateway
        def uppercase_in(text: str):
            return (text.upper(),), {}

        @rt.function_node(middleware=MiddlewareSet(gateway_entry=[uppercase_in]))
        def echo(text: str) -> str:
            return text

        result = await rt.Flow("test_echo", echo).ainvoke("hello")

        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_exit_gateway_transforms_output(self):
        """Exit gateway can rewrite the return value after the function returns."""

        @rt.gateway
        def double_out(result: int) -> int:
            return result * 2

        @rt.function_node(middleware=MiddlewareSet(gateway_exit=[double_out]))
        def add(x: int, y: int) -> int:
            return x + y

        result = await rt.Flow("test_add", add).ainvoke(3, 4)

        assert result == 14  # (3 + 4) * 2

    @pytest.mark.asyncio
    async def test_entry_gateway_check_only_passes_through(self):
        """A check-only entry gateway (returns None) leaves args unchanged."""

        checked = {"called": False}

        @rt.gateway
        def just_check(x: int, y: int):
            checked["called"] = True
            # returning None = check-only; args pass through unchanged

        @rt.function_node(middleware=MiddlewareSet(gateway_entry=[just_check]))
        def add(x: int, y: int) -> int:
            return x + y

        result = await rt.Flow("test_add_check", add).ainvoke(3, 4)

        assert result == 7
        assert checked["called"]

    @pytest.mark.asyncio
    async def test_entry_gateway_guardrail_raises(self):
        """Entry gateway acting as a guardrail propagates its exception to the caller."""

        @rt.gateway
        def no_negatives(x: int, y: int):
            if x < 0 or y < 0:
                raise ValueError("Negative numbers not allowed")

            return (x, y), {}

        @rt.function_node(middleware=MiddlewareSet(gateway_entry=[no_negatives]))
        def add(x: int, y: int) -> int:
            return x + y

        with pytest.raises(ValueError, match="Negative"):
            await rt.Flow("test_add_guardrail", add).ainvoke(-1, 5)

    @pytest.mark.asyncio
    async def test_wrapper_retries_on_failure(self):
        """Wrapper can catch exceptions and retry the inner call."""

        attempt = {"count": 0}

        @rt.wrapper
        def retry_once(call):
            async def _inner(*args, **kwargs):
                try:
                    return await call(*args, **kwargs)
                except ValueError:
                    return await call(*args, **kwargs)
            return _inner

        @rt.function_node(middleware=MiddlewareSet(wrappers=[retry_once]))
        async def flaky() -> str:
            attempt["count"] += 1
            if attempt["count"] < 2:
                raise ValueError("not ready")
            return "ok"

        result = await rt.Flow("test_flaky", flaky).ainvoke()

        assert result == "ok"
        assert attempt["count"] == 2

    @pytest.mark.asyncio
    async def test_wrapper_short_circuits(self):
        """Wrapper can skip the inner call entirely and return its own result."""

        @rt.wrapper
        def block(call):
            async def _inner(*args, **kwargs):
                return "blocked"
            return _inner

        @rt.function_node(middleware=MiddlewareSet(wrappers=[block]))
        async def should_not_run() -> str:
            raise AssertionError("core should not be called")

        result = await rt.Flow("test_block", should_not_run).ainvoke()

        assert result == "blocked"

    @pytest.mark.asyncio
    async def test_full_band_ordering(self):
        """Wrappers → entry gateways → inner_wrappers → core → exit gateways → outer unwind."""

        log = []

        @rt.wrapper
        def outer_wrap(call):
            async def _inner(*args, **kwargs):
                log.append("outer_before")
                result = await call(*args, **kwargs)
                log.append("outer_after")
                return result
            return _inner

        @rt.gateway
        def entry_gw(x: int):
            log.append("entry")
            return (x,), {}

        @rt.wrapper
        def inner_wrap(call):
            async def _inner(*args, **kwargs):
                log.append("inner_before")
                result = await call(*args, **kwargs)
                log.append("inner_after")
                return result
            return _inner

        @rt.gateway
        def exit_gw(result: int):
            log.append("exit")
            return result

        ms = MiddlewareSet(
            wrappers=[outer_wrap],
            gateway_entry=[entry_gw],
            inner_wrappers=[inner_wrap],
            gateway_exit=[exit_gw],
        )

        @rt.function_node(middleware=ms)
        def core(x: int) -> int:
            log.append("core")
            return x + 1

        result = await rt.Flow("test_band_order", core).ainvoke(5)

        assert result == 6
        assert log == [
            "outer_before",
            "entry",
            "inner_before",
            "core",
            "inner_after",
            "exit",
            "outer_after",
        ]

    @pytest.mark.asyncio
    async def test_multiple_wrappers_outer_to_inner_order(self):
        """First wrapper in the list is outermost; list order = outer-to-inner."""

        log = []

        @rt.wrapper
        def first(call):
            async def _inner(*args, **kwargs):
                log.append("first_before")
                result = await call(*args, **kwargs)
                log.append("first_after")
                return result
            return _inner

        @rt.wrapper
        def second(call):
            async def _inner(*args, **kwargs):
                log.append("second_before")
                result = await call(*args, **kwargs)
                log.append("second_after")
                return result
            return _inner

        @rt.function_node(middleware=MiddlewareSet(wrappers=[first, second]))
        def identity(x: int) -> int:
            log.append("core")
            return x

        await rt.Flow("test_wrapper_order", identity).ainvoke(0)

        assert log == [
            "first_before",
            "second_before",
            "core",
            "second_after",
            "first_after",
        ]

    @pytest.mark.asyncio
    async def test_multiple_entry_gateways_apply_sequentially(self):
        """Multiple entry gateways run in list order; each transforms what the previous produced."""

        @rt.gateway
        def add_one(x: int):
            return (x + 1,), {}

        @rt.gateway
        def double(x: int):
            return (x * 2,), {}

        @rt.function_node(middleware=MiddlewareSet(gateway_entry=[add_one, double]))
        def identity(x: int) -> int:
            return x  # receives (x+1)*2

        result = await rt.Flow("test_entry_gw_chain", identity).ainvoke(3)  # (3+1)*2 = 8

        assert result == 8

    @pytest.mark.asyncio
    async def test_multiple_exit_gateways_apply_sequentially(self):
        """Multiple exit gateways chain: first transforms, second transforms the result."""

        @rt.gateway
        def add_ten(result: int) -> int:
            return result + 10

        @rt.gateway
        def negate(result: int) -> int:
            return -result

        @rt.function_node(middleware=MiddlewareSet(gateway_exit=[add_ten, negate]))
        def five() -> int:
            return 5  # → +10 = 15 → negate = -15

        result = await rt.Flow("test_exit_gw_chain", five).ainvoke()

        assert result == -15

    @pytest.mark.asyncio
    async def test_gateway_args_explicit_with_kwargs(self):
        """gateway.args() lets an entry gateway specify both positional and keyword args."""

        @rt.gateway
        def swap_and_flag(a: int, b: int):
            return rt.gateway.args(b, a, flag=True)

        @rt.function_node(
            middleware=MiddlewareSet(gateway_entry=[swap_and_flag])
        )
        def compute(a: int, b: int, flag: bool = False) -> str:
            return f"{a}-{b}-{flag}"

        result = await rt.Flow("test_gateway_args", compute).ainvoke(3, 10)  # swap → (10, 3, flag=True)

        assert result == "10-3-True"

    @pytest.mark.asyncio
    async def test_async_entry_gateway(self):
        """Entry gateways may be async; they are awaited correctly."""

        @rt.gateway
        async def async_double_input(x: int):
            await asyncio.sleep(0)
            return (x * 2,), {}

        @rt.function_node(middleware=MiddlewareSet(gateway_entry=[async_double_input]))
        def identity(x: int) -> int:
            return x

        result = await rt.Flow("test_async_entry", identity).ainvoke(5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_async_exit_gateway(self):
        """Exit gateways may be async; they are awaited correctly."""

        @rt.gateway
        async def async_double_output(result: int) -> int:
            await asyncio.sleep(0)
            return result * 2

        @rt.function_node(middleware=MiddlewareSet(gateway_exit=[async_double_output]))
        def three() -> int:
            return 3

        result = await rt.Flow("test_async_exit", three).ainvoke()

        assert result == 6

    @pytest.mark.asyncio
    async def test_middleware_set_coerce_from_bare_list(self):
        """MiddlewareSet.coerce() routes Gateways→gateway_entry and Wrappers→wrappers."""

        # coerce puts Gateways into gateway_entry (not gateway_exit), so the
        # gateway must have an entry signature: receives the function's input args.
        @rt.gateway
        def double_x(x: int):
            return (x * 2,), {}

        @rt.function_node(middleware=MiddlewareSet.coerce([double_x]))
        def identity(x: int) -> int:
            return x

        result = await rt.Flow("test_coerce", identity).ainvoke(7)

        assert result == 14


# ---------------------------------------------------------------------------
# TestAgentNodeMiddleware
# ---------------------------------------------------------------------------


class TestAgentNodeMiddleware:
    """Middleware at the agent node boundary (user_input → StringResponse/StructuredResponse)."""

    @pytest.mark.asyncio
    async def test_node_level_exit_gateway_fires_after_response(self, mock_llm):
        """Node-level exit gateway is called after the full agent response is ready."""

        side_effects = {"called": False}

        @rt.gateway
        def mark_called(response):
            side_effects["called"] = True
            # None = check-only, pass response through unchanged

        agent = rt.agent_node(
            name="ExitGWAgent",
            llm=mock_llm(custom_response="hello"),
            middleware=MiddlewareSet(gateway_exit=[mark_called]),
        )

        result = await rt.Flow("ExitGWAgent", agent).ainvoke("hi")

        assert side_effects["called"]
        assert "hello" in result.content

    @pytest.mark.asyncio
    async def test_node_level_wrapper_around_agent(self, mock_llm):
        """Node-level wrapper wraps the entire agent invocation."""

        call_count = {"n": 0}

        @rt.wrapper
        def count_calls(call):
            async def _inner(*args, **kwargs):
                call_count["n"] += 1
                return await call(*args, **kwargs)
            return _inner

        agent = rt.agent_node(
            name="CountedAgent",
            llm=mock_llm(custom_response="done"),
            middleware=MiddlewareSet(wrappers=[count_calls]),
        )

        await rt.Flow("CountedAgent", agent).ainvoke("run once")

        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_node_level_guardrail_blocks_call(self, mock_llm):
        """Node-level entry gateway raises before the LLM is ever called."""

        llm_called = {"value": False}

        @rt.gateway
        def block_all(user_input):
            raise PermissionError("Access denied")

        class TrackingLLM(type(mock_llm())):
            def _chat(self, messages, **kwargs):
                llm_called["value"] = True
                return super()._chat(messages, **kwargs)

        agent = rt.agent_node(
            name="BlockedAgent",
            llm=mock_llm(custom_response="should not appear"),
            middleware=MiddlewareSet(gateway_entry=[block_all]),
        )

        with pytest.raises(PermissionError, match="Access denied"):
            await rt.Flow("BlockedAgent", agent).ainvoke("attempt this")

        assert not llm_called["value"]

    @pytest.mark.asyncio
    async def test_structured_output_agent_with_exit_gateway(self, mock_llm):
        """Exit gateway receives the StructuredResponse and can inspect it."""

        class Answer(BaseModel):
            value: int = Field(description="The answer")

        captured = {}

        @rt.gateway
        def capture_response(response):
            captured["response"] = response

        agent = rt.agent_node(
            name="StructuredAgent",
            llm=mock_llm(custom_response='{"value": 42}'),
            output_schema=Answer,
            middleware=MiddlewareSet(gateway_exit=[capture_response]),
        )

        result = await rt.Flow("StructuredAgent", agent).ainvoke("what is the answer?")

        assert result.structured.value == 42
        assert captured["response"] is result


# ---------------------------------------------------------------------------
# TestModelMiddleware
# ---------------------------------------------------------------------------


class TestModelMiddleware:
    """Middleware around each raw model call (messages/schema/tools → Response)."""

    @pytest.mark.asyncio
    async def test_model_middleware_wrapper_invoked_per_llm_call(self, mock_llm):
        """A model_middleware wrapper runs once per raw model invocation."""

        invocations = {"n": 0}

        @rt.wrapper
        def count_model_calls(call):
            async def _inner(messages, schema, tools):
                invocations["n"] += 1
                return await call(messages, schema, tools)
            return _inner

        agent = rt.agent_node(
            name="CountedModel",
            llm=mock_llm(custom_response="reply"),
            model_middleware=MiddlewareSet(wrappers=[count_model_calls]),
        )

        await rt.Flow("CountedModel", agent).ainvoke("hello")

        assert invocations["n"] == 1

    @pytest.mark.asyncio
    async def test_model_middleware_entry_gateway_can_inspect_messages(self, mock_llm):
        """Model-level entry gateway sees the full MessageHistory before the model call."""

        seen_roles = []

        @rt.gateway
        async def capture_roles(messages, schema, tools):
            for m in messages:
                seen_roles.append(m.role)
            # None = check-only

        agent = rt.agent_node(
            name="RoleCapture",
            llm=mock_llm(custom_response="ok"),
            system_message="You are a helper.",
            model_middleware=MiddlewareSet(gateway_entry=[capture_roles]),
        )

        await rt.Flow("RoleCapture", agent).ainvoke("question")

        assert "system" in seen_roles
        assert "user" in seen_roles

    @pytest.mark.asyncio
    async def test_model_middleware_entry_gateway_can_modify_messages(self, mock_llm):
        """Model-level entry gateway can inject or rewrite messages."""

        received_content = []

        @rt.gateway
        async def inject_header(messages, schema, tools):
            from railtracks.llm.message import UserMessage
            from railtracks.llm.history import MessageHistory

            new_messages = MessageHistory(list(messages))
            new_messages.insert(0, UserMessage("[INJECTED]"))
            return (new_messages, schema, tools), {}

        @rt.gateway
        async def capture_first_message(messages, schema, tools):
            received_content.append(messages[0].content)
            # check-only after capture

        agent = rt.agent_node(
            name="InjectionAgent",
            llm=mock_llm(custom_response="ok"),
            model_middleware=MiddlewareSet(
                gateway_entry=[inject_header, capture_first_message]
            ),
        )

        await rt.Flow("InjectionAgent", agent).ainvoke("actual question")

        assert received_content[0] == "[INJECTED]"

    @pytest.mark.asyncio
    async def test_model_middleware_wrapper_can_retry_on_llm_error(self, mock_llm):
        """Model-level wrapper can catch model errors and retry.

        model_middleware wraps _core_llm_call directly, so the wrapper sees the
        raw Exception from the model — LLMError wrapping happens one layer above
        in llm_invoke_factory after the middleware stack unwinds.
        """

        from railtracks.exceptions.errors import LLMError

        attempts = {"n": 0}

        @rt.wrapper
        def retry_llm(call):
            async def _inner(messages, schema, tools):
                for _ in range(3):
                    try:
                        return await call(messages, schema, tools)
                    except Exception:
                        attempts["n"] += 1
                raise LLMError(reason="exhausted", message_history=messages)
            return _inner

        # First call raises, second succeeds
        llm = mock_llm(
            custom_response="success",
            errors=[lambda: Exception("transient network error")],
        )

        agent = rt.agent_node(
            name="RetryAgent",
            llm=llm,
            model_middleware=MiddlewareSet(wrappers=[retry_llm]),
        )

        result = await rt.Flow("RetryAgent", agent).ainvoke("try this")

        assert "success" in result.content
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_model_middleware_independent_per_agent_node(self, mock_llm):
        """Each agent node gets its own copy of model_middleware; sys gateways don't cross-contaminate."""

        gateway_a_calls = {"n": 0}
        gateway_b_calls = {"n": 0}

        @rt.gateway
        async def gw_a(messages, schema, tools):
            gateway_a_calls["n"] += 1

        @rt.gateway
        async def gw_b(messages, schema, tools):
            gateway_b_calls["n"] += 1

        agent_a = rt.agent_node(
            "AgentA",
            llm=mock_llm(custom_response="a"),
            model_middleware=MiddlewareSet(gateway_entry=[gw_a]),
        )
        agent_b = rt.agent_node(
            "AgentB",
            llm=mock_llm(custom_response="b"),
            model_middleware=MiddlewareSet(gateway_entry=[gw_b]),
        )

        await rt.Flow("AgentA", agent_a).ainvoke("hello")
        await rt.Flow("AgentB", agent_b).ainvoke("hello")

        assert gateway_a_calls["n"] == 1
        assert gateway_b_calls["n"] == 1


# ---------------------------------------------------------------------------
# TestContextInjection
# ---------------------------------------------------------------------------


class TestContextInjection:
    """Context injection: rt.context variables substituted into prompt templates."""

    @pytest.mark.asyncio
    async def test_context_variable_injected_into_system_message(self, mock_llm):
        """rt.context values are substituted into {placeholder} template syntax before the LLM call."""

        injected_system_content = []

        @rt.gateway
        async def capture_system(messages, schema, tools):
            for m in messages:
                if m.role == "system":
                    injected_system_content.append(m.content)

        agent = rt.agent_node(
            name="TemplateAgent",
            llm=mock_llm(custom_response="done"),
            system_message="You assist {username}.",
            model_middleware=MiddlewareSet(gateway_entry=[capture_system]),
        )

        await rt.Flow("TemplateAgent", agent, context={"username": "Alice"}).ainvoke("help me")

        assert any("Alice" in c for c in injected_system_content)

    @pytest.mark.asyncio
    async def test_context_injection_disabled_when_flag_is_false(self, mock_llm):
        """context_injection=False prevents {placeholder} substitution."""

        injected_system_content = []

        @rt.gateway
        async def capture_system(messages, schema, tools):
            for m in messages:
                if m.role == "system":
                    injected_system_content.append(m.content)

        agent = rt.agent_node(
            name="NoInjectionAgent",
            llm=mock_llm(custom_response="done"),
            system_message="You assist {username}.",
            model_middleware=MiddlewareSet(gateway_entry=[capture_system]),
            context_injection=False,
        )

        await rt.Flow("NoInjectionAgent", agent, context={"username": "Alice"}).ainvoke("help me")

        assert all("{username}" in c for c in injected_system_content)


# ---------------------------------------------------------------------------
# TestModelSourceFactory
# ---------------------------------------------------------------------------


class TestModelSourceFactory:
    """ModelSource can be a no-arg callable resolved fresh on every model call."""

    @pytest.mark.asyncio
    async def test_model_factory_resolved_per_agent_call(self, mock_llm):
        """A factory ModelSource is called once per agent invocation."""

        factory_calls = {"n": 0}

        def llm_factory():
            factory_calls["n"] += 1
            return mock_llm(custom_response=f"response_{factory_calls['n']}")

        agent = rt.agent_node(name="FactoryAgent", llm=llm_factory)

        flow = rt.Flow("FactoryAgent", agent)
        r1 = await flow.ainvoke("first call")
        r2 = await flow.ainvoke("second call")

        assert factory_calls["n"] == 2
        assert "response_1" in r1.content
        assert "response_2" in r2.content


# ---------------------------------------------------------------------------
# TestToolCallingWithPrepareArgs
# ---------------------------------------------------------------------------


class TestToolCallingWithPrepareArgs:
    """End-to-end tool calling via the NodeBuilder path (verifies prepare_args fix)."""

    @pytest.mark.asyncio
    async def test_function_node_tool_called_with_correct_args(self, mock_llm):
        """Agent dispatches a tool call; the function node receives correctly typed arguments."""

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
            name="DoubleAgent",
            llm=llm,
            tool_nodes=[rt.function_node(double)],
        )

        result = await rt.Flow("DoubleAgent", agent).ainvoke("double 5")

        assert received.get("n") == 5
        assert "10" in result.content

    @pytest.mark.asyncio
    async def test_multiple_parallel_tool_calls(self, mock_llm):
        """Agent dispatching multiple tool calls in one response runs them all."""

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
        agent = rt.agent_node(
            name="MultiToolAgent",
            llm=llm,
            tool_nodes=[rt.function_node(tag)],
        )

        await rt.Flow("MultiToolAgent", agent).ainvoke("tag alpha and beta")

        assert sorted(calls_made) == ["alpha", "beta"]

    @pytest.mark.asyncio
    async def test_tool_exception_surfaced_to_llm_as_string(self, mock_llm):
        """Tool runtime errors become error-string ToolMessages; the LLM loop continues."""

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
            name="ErrorToolAgent",
            llm=llm,
            tool_nodes=[rt.function_node(always_fails)],
        )

        result = await rt.Flow("ErrorToolAgent", agent).ainvoke("call always_fails")

        # The error is surfaced to the LLM as a tool message string, not raised.
        assert result is not None

    @pytest.mark.asyncio
    async def test_function_node_tool_with_middleware_executes_middleware(
        self, mock_llm
    ):
        """Middleware on a function node tool fires when the tool is called by an agent."""

        gateway_fired = {"value": False}

        @rt.gateway
        def mark_fired(n: int):
            gateway_fired["value"] = True

        def increment(n: int) -> int:
            """Increments a number.
            Args:
                n (int): The number.
            Returns:
                int: n + 1.
            """
            return n + 1

        tool = rt.function_node(
            increment, middleware=MiddlewareSet(gateway_entry=[mark_fired])
        )

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="increment", identifier="id_inc", arguments={"n": 9})
            ]
        )
        agent = rt.agent_node(
            name="ToolWithMiddlewareAgent",
            llm=llm,
            tool_nodes=[tool],
        )

        result = await rt.Flow("ToolWithMiddlewareAgent", agent).ainvoke("increment 9")

        assert gateway_fired["value"]
        assert "10" in result.content


# ---------------------------------------------------------------------------
# TestMiddlewareSetIsolation
# ---------------------------------------------------------------------------


class TestMiddlewareSetIsolation:
    """MiddlewareSet fresh-copy semantics: sharing a set across nodes is safe."""

    def test_shared_middleware_set_not_mutated(self, mock_llm):
        """Two nodes built from the same MiddlewareSet get independent copies."""

        shared = MiddlewareSet()

        node_a = rt.agent_node("IsoA", llm=mock_llm(), middleware=shared)
        node_b = rt.agent_node("IsoB", llm=mock_llm(), middleware=shared)

        assert node_a.frozen_middleware is not node_b.frozen_middleware
        assert node_a.frozen_middleware is not shared

    def test_node_instance_middleware_independent_from_class(self, mock_llm):
        """Each Node instance gets a fresh copy of frozen_middleware; mutations don't bleed."""

        agent_cls = rt.agent_node("InstanceIso", llm=mock_llm())
        instance_a = agent_cls()
        instance_b = agent_cls()

        assert instance_a.middleware is not instance_b.middleware
        assert instance_a.middleware is not agent_cls.frozen_middleware

    @pytest.mark.asyncio
    async def test_sys_gateway_registered_once_per_node(self, mock_llm):
        """System-registered gateways (e.g. context injection) do not accumulate across builds."""

        call_count = {"n": 0}

        @rt.gateway
        async def counting_gw(messages, schema, tools):
            call_count["n"] += 1

        # Build the same agent multiple times with the same model_middleware
        ms = MiddlewareSet(gateway_entry=[counting_gw])

        for _ in range(3):
            agent = rt.agent_node(
                name="AccumTest",
                llm=mock_llm(custom_response="ok"),
                model_middleware=ms,
            )
            await rt.Flow("AccumTest", agent).ainvoke("hi")

        # counting_gw fires exactly once per call, 3 calls total
        assert call_count["n"] == 3
