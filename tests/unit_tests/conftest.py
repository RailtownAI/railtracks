import pytest
from pathlib import Path
import shutil



@pytest.fixture(scope="session", autouse=True)
def global_teardown():
    # Setup code (before tests run)
    yield
    # Teardown code (after all tests run)
    covailence_dir = Path(".covailence")
    if covailence_dir.exists() and covailence_dir.is_dir():
        shutil.rmtree(covailence_dir)
        print("Cleaned up .covailence directory after tests.")