import pytest
import railtracks as rt
import asyncio
import time


def timeout_node(t_: float):
    time.sleep(t_)
    return t_


async def timeout_node_async(t_: float):
    await asyncio.sleep(t_)
    return t_


TimeoutNode = rt.library.from_function(timeout_node)
TimeoutNodeAsync = rt.library.from_function(timeout_node_async)


async def top_level_async():
    uno = rt.call(TimeoutNodeAsync, 1)
    dos = rt.call(TimeoutNodeAsync, 2)
    tres = rt.call(TimeoutNodeAsync, 3)
    quatro = rt.call(TimeoutNodeAsync, 2)
    cinco = rt.call(TimeoutNodeAsync, 1)

    result = await asyncio.gather(uno, dos, tres, quatro, cinco)

    return result


async def top_level():
    uno = rt.call(TimeoutNode, 1)
    dos = rt.call(TimeoutNode, 2)
    tres = rt.call(TimeoutNode, 3)
    quatro = rt.call(TimeoutNode, 2)
    cinco = rt.call(TimeoutNode, 1)

    result = await asyncio.gather(uno, dos, tres, quatro, cinco)

    return result


TopLevelAsync = rt.library.from_function(top_level_async)
TopLevel = rt.library.from_function(top_level)


@pytest.mark.timeout(4)
@pytest.mark.parametrize("node", [TopLevel, TopLevelAsync], ids=["sync", "async"])
def test_async_style_parallel(node):
    with rt.Runner(rt.ExecutorConfig(logging_setting="NONE")) as run:
        result = run.run_sync(node)
        assert result.answer == [1, 2, 3, 2, 1]


@pytest.mark.timeout(4)
@pytest.mark.asyncio
@pytest.mark.parametrize("node", [TopLevel, TopLevelAsync], ids=["sync", "async"])
async def test_async_style_parallel_2(node):
    with rt.Runner() as run:
        result = await run.run(node)
        assert result.answer == [1, 2, 3, 2, 1]
