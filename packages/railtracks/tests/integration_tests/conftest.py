import pytest
from pathlib import Path
import shutil



@pytest.fixture(scope="session", autouse=True)
def global_teardown():
    # Setup code (before tests run)
    yield
    # Teardown code (after all tests run)
    railtracks_dir = Path(".railtracks")
    if railtracks_dir.exists() and railtracks_dir.is_dir():
        shutil.rmtree(railtracks_dir)
        print("Cleaned up .railtracks directory after tests.")