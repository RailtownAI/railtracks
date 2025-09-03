#!/usr/bin/env python3

"""
Simple test runner for railtracks-cli tests
"""

import sys
import unittest
from pathlib import Path


def run_tests():
    """Run all tests in the tests directory"""
    # Add src to path so tests can import railtracks_cli
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))

    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent / "tests"
    suite = loader.discover(str(start_dir), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
