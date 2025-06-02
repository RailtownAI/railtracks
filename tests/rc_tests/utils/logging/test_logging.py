import random
import asyncio

import pytest
import src.requestcompletion as rc
import re


RNGNode = rc.library.from_function(random.random)


def strip_ansi_colors(message: str) -> str:
    """
    Removes ANSI color codes from the given message.
    """
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', message)


async def top_level(number_of_calls: int):

    contracts = [rc.call(RNGNode) for _ in range(number_of_calls)]

    random_numbers = await asyncio.gather(*contracts)

    return random_numbers


TopLevelNode = rc.library.from_function(top_level)


def test_simple_request(caplog):
    with rc.Runner() as run:
        result = run.run_sync(RNGNode)

    stripped_messages = [strip_ansi_colors(msg) for msg in caplog.messages]

    # one for start and one for end
    assert len(stripped_messages) == 2
    assert stripped_messages[0] == "START CREATED random Node - (, )"
    assert stripped_messages[1] == f"random Node DONE {result.answer}"

    assert isinstance(result.answer, float)


def test_more_complex_request(caplog):
    subcalls = 10
    with rc.Runner() as run:
        result = run.run_sync(TopLevelNode, subcalls)

    stripped_messages = [strip_ansi_colors(msg) for msg in caplog.messages]

    assert len(stripped_messages) == subcalls * 2 + 2
    assert stripped_messages[0] == "START CREATED top_level Node - (10, )"
    assert stripped_messages[1] == "top_level Node CREATED random Node - (, )"
    assert stripped_messages[-1] == f"top_level Node DONE {result.answer}"


def test_more_complex_request_regular(caplog):
    subcalls = 10
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="REGULAR")) as run:
        result = run.run_sync(TopLevelNode, subcalls)

    stripped_messages = [strip_ansi_colors(msg) for msg in caplog.messages]

    assert len(caplog.messages) == subcalls * 2 + 2
    assert stripped_messages[0] == "START CREATED top_level Node - (10, )"
    assert stripped_messages[1] == "top_level Node CREATED random Node - (, )"
    assert stripped_messages[-1] == f"top_level Node DONE {result.answer}"


def test_more_complex_request_regular_quiet(caplog):
    subcalls = 10
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="QUIET")) as run:
        result = run.run_sync(TopLevelNode, subcalls)

    stripped_messages = [strip_ansi_colors(msg) for msg in caplog.messages]

    assert len(stripped_messages) == 0


def test_more_complex_request_regular_none(caplog):
    subcalls = 10
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as run:
        result = run.run_sync(TopLevelNode, subcalls)

    stripped_messages = [strip_ansi_colors(msg) for msg in caplog.messages]

    assert len(stripped_messages) == 0
