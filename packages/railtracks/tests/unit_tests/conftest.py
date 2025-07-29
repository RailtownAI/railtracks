from typing import Callable, List, Type

import pytest
from pathlib import Path
import shutil

from railtracks.llm import MessageHistory, Tool
from railtracks.llm.response import Response
import railtracks.llm as llm

from pydantic import BaseModel


@pytest.fixture(scope="session", autouse=True)
def global_teardown():
    # Setup code (before tests run)
    yield
    # Teardown code (after all tests run)
    railtracks_dir = Path(".railtracks")
    if railtracks_dir.exists() and railtracks_dir.is_dir():
        shutil.rmtree(railtracks_dir)
        print("Cleaned up .railtracks directory after tests.")


# ====================================== MockLLM ======================================


# ===================================== END MockLLM ======================================