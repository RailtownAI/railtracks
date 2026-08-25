import pytest 
import asyncio
from unittest.mock import patch
from railtracks.pubsub.publisher import Publisher, RTPublisher
from railtracks.pubsub.messages import BroadcastEvent

# ================================== Pub Sub Fixtures ==================================
@pytest.fixture
def sync_callback_container():
    """Container for a simple mutable value, with a registered callback function."""
    state = {'value': None}
    def callback(x):
        state['value'] = x
    return state, callback

@pytest.fixture
def async_callback_container():
    state = {'value': None}
    async def callback(x):
        await asyncio.sleep(0.01)
        state['value'] = x
    return state, callback

@pytest.fixture
def msg_list_container():
    """For collecting callback messages in order."""
    state = []
    def callback(x):
        state.append(x)
    return state, callback

@pytest.fixture
async def started_publisher():
    """Auto-started instance of Publisher (shuts down after)."""
    pub = Publisher()
    await pub.start()
    yield pub
    await pub.shutdown()

@pytest.fixture
async def async_publisher():
    async with Publisher() as pub:
        yield pub

@pytest.fixture
def event_item():
    class DummyItem: pass
    return DummyItem()

@pytest.fixture
def broadcast_event(event_item):
    return BroadcastEvent(item=event_item, node_id="123")
