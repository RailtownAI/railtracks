import pytest
from unittest.mock import Mock, AsyncMock, patch

@pytest.fixture
def mock_publisher():
    """Fixture providing a mock publisher with async methods."""
    publisher = Mock()
    publisher.publish = AsyncMock()
    publisher.listener = AsyncMock()
    return publisher


@pytest.fixture
def mock_config():
    """Fixture providing a mock configuration object."""
    config = Mock()
    config.timeout = 0.01
    return config


@pytest.fixture
def mock_context_functions():
    """Fixture that patches all context-related functions."""
    with patch('railtracks.interaction._call.is_context_present') as present, \
         patch('railtracks.interaction._call.is_context_active') as active, \
         patch('railtracks.interaction._call.activate_publisher') as activate, \
         patch('railtracks.interaction._call.shutdown_publisher') as shutdown, \
         patch('railtracks.interaction._call.get_publisher') as get_pub, \
         patch('railtracks.interaction._call.get_parent_id') as get_parent, \
         patch('railtracks.interaction._call.get_run_id') as get_run, \
         patch('railtracks.interaction._call.get_local_config') as get_config:
        
        # Set default return values
        get_parent.return_value = "parent_123"
        get_run.return_value = "run_456"
        
        yield {
            'is_context_present': present,
            'is_context_active': active,
            'activate_publisher': activate,
            'shutdown_publisher': shutdown,
            'get_publisher': get_pub,
            'get_parent_id': get_parent,
            'get_local_config': get_config
        }



@pytest.fixture
def mock_execute():
    """Fixture that patches the _execute function."""
    with patch('railtracks.interaction._call._execute') as execute:
        yield execute


@pytest.fixture
def mock_start():
    """Fixture that patches the _start function."""
    with patch('railtracks.interaction._call._start') as start:
        yield start


@pytest.fixture
def mock_run():
    """Fixture that patches the _run function."""
    with patch('railtracks.interaction._call._run') as run:
        yield run


@pytest.fixture
def full_context_setup(mock_context_functions, mock_publisher, mock_config):
    """Fixture that provides a complete context setup for integration tests."""
    mock_context_functions['get_publisher'].return_value = mock_publisher
    mock_context_functions['get_local_config'].return_value = mock_config
    return {
        'context': mock_context_functions,
        'publisher': mock_publisher,
        'config': mock_config
    }
