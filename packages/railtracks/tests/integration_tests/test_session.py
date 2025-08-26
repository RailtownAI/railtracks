import pytest
import railtracks as rt


def example_1():
    return "hello world"


def example_2():
    return "goodbye world"


E1 = rt.function_node(example_1)
E2 = rt.function_node(example_2)


@pytest.mark.asyncio
async def test_multiple_sessions_ids_distinct():
    with rt.Session() as sess1:
        await rt.call(E1)

    with rt.Session() as sess2:
        await rt.call(E2)

    assert sess1._identifier != sess2._identifier, (
        "Session identifiers should be distinct"
    )
