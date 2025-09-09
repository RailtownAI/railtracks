#!/bin/bash

# License checking script for Railtracks
# This script checks for disallowed licenses in project dependencies

set -euo pipefail

# Configuration
DISALLOWED_LICENSES="GPL|AGPL|EPL"
VENV_DIR=".venv"
CORE_LICENSES_FILE="core-licenses.md"
CORE_LICENSES_SUMMARY_FILE="core-licenses-summary.md"


echo "Starting license check for Railtracks dependencies..."

# Clean up any existing virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "Cleaning up existing virtual environment..."
    rm -rf "$VENV_DIR"
fi

# Create isolated virtual environment
echo "Creating isolated virtual environment..."
python -m venv "$VENV_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install only the core railtracks package and its dependencies
echo "Installing Railtracks core package and dependencies..."
pip install -e packages/railtracks

# Install pip-licenses for license checking
echo "Installing pip-licenses..."
pip install pip-licenses

# Generate license report
echo "Generating license report..."
pip-licenses --format=markdown > "$CORE_LICENSES_FILE"

# Check for disallowed licenses
echo "Checking for disallowed licenses..."
if grep -E "$DISALLOWED_LICENSES" "$CORE_LICENSES_FILE"; then
    echo "ERROR: Disallowed licenses found in dependencies:"
    grep -E "$DISALLOWED_LICENSES" "$CORE_LICENSES_FILE"

    # Clean up
    deactivate
    rm -rf "$VENV_DIR"
    exit 1
else
    echo "No disallowed licenses found in dependencies"
fi

# Generate license summary
echo "Generating license summary..."
pip-licenses --summary --format=markdown > "$CORE_LICENSES_SUMMARY_FILE"

# Display summary
echo "License Summary:"
cat "$CORE_LICENSES_SUMMARY_FILE"

echo ""
echo "Full License Report:"
cat "$CORE_LICENSES_FILE"

# Clean up virtual environment
echo "Cleaning up virtual environment..."

deactivate
rm -rf "$VENV_DIR"

echo "License check completed successfully!"
