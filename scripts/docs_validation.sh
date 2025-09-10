#!/bin/bash

# Script to validate that all documentation scripts in docs/scripts/ can execute successfully

set -e  # Exit on any error

echo "Starting documentation scripts validation..."

# Check if we're in the right directory
if [ ! -d "docs/scripts" ]; then
    echo "Error: docs/scripts directory not found!"
    exit 1
fi

DISABLE_CODES="top-level-await"
mypy --disable-error-code=top-level-await --disable-error-code=import-untyped docs/scripts/



