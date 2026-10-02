"""Run mypy over ``typing_cases.py``: descriptor answers and decision_node overloads.

Opt-in with ``RAILTRACKS_TYPECHECK=1``: mypy has to analyse the whole package, which
takes minutes on a cold cache.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RAILTRACKS_TYPECHECK") != "1",
    reason="set RAILTRACKS_TYPECHECK=1 to run the mypy typing check",
)

CASES = Path(__file__).with_name("typing_cases.py")


@pytest.mark.timeout(900)
def test_typing_cases_pass_mypy():
    api = pytest.importorskip("mypy.api")
    stdout, stderr, status = api.run(
        [
            str(CASES),
            "--warn-unused-ignores",
            "--no-error-summary",
            "--disable-error-code=import-untyped",
        ]
    )
    assert status == 0, stdout + stderr
