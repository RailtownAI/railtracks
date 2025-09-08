import asyncio
import pytest
from railtracks.nodes.nodes import DebugDetails, Node

from railtracks.context.central import get_session_id, get_run_id, get_parent_id
import railtracks as rt


class BottomLevel(Node):
    def __init__(self,  expected_session_id: str | None, expected_run_id: str | None):
        super().__init__()
        self.expected_session_id = expected_session_id
        self.expected_run_id = expected_run_id

    async def invoke(self):
        session_id = get_session_id()
        run_id = get_run_id()
        parent_id = get_parent_id()

        assert session_id == self.expected_session_id
        assert run_id == self.expected_run_id
        assert parent_id == self.uuid

        return {
            "session_id": session_id,
            "run_id": run_id,
            "parent_id": parent_id
        }
    
    @classmethod
    def name(cls):
        return "Top Level"
    
    @classmethod
    def type(cls):
        return "Tool"


class TopLevel(Node):
    def __init__(self, number_trials: int, expected_session_id: str | None):
        super().__init__()
        self.expected_session_id = expected_session_id
        self.number_trials = number_trials

    async def invoke(self):
        session_id = get_session_id()
        run_id = get_run_id()
        parent_id = get_parent_id()

        assert session_id == self.expected_session_id
        assert run_id == self.uuid
        assert parent_id == self.uuid
        contracts = [rt.call(BottomLevel, self.expected_session_id, self.uuid) for _ in range(self.number_trials)]
        return await asyncio.gather(*contracts)
    
    @classmethod
    def name(cls):
        return "Top Level"
    
    @classmethod
    def type(cls):
        return "Tool"


@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5, 10, 50])
async def test_run_id_propagation(num_trials):
    
    with rt.Session(name="test_session", logging_setting="NONE") as session:
        await rt.call(TopLevel, num_trials, session._identifier)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_runs(num_trials):
    
    with rt.Session(name="test_session", logging_setting="NONE") as session:
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_runs_parallel(num_trials):
    
    with rt.Session(name="test_session", logging_setting="NONE") as session:
        contracts = [rt.call(TopLevel, num_trials, session._identifier) for _ in range(4)]
        await asyncio.gather(*contracts)



@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_sessions(num_trials):
    
    with rt.Session(name="test_session", logging_setting="NONE") as session:
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)

    with rt.Session(name="test_session_2", logging_setting="NONE") as session:
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)

@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_sessions_parallel(num_trials):

    async def runner():
    
        with rt.Session(name="test_session", logging_setting="NONE") as session:
            await rt.call(TopLevel, num_trials, session._identifier)
            await rt.call(TopLevel, num_trials, session._identifier)
        

    await asyncio.gather(runner(), runner())