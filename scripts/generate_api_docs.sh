#!/bin/bash

# Railtracks API Documentation Generator

set -e  # Exit on any error

echo "Generating Railtracks API Documentation..."

# Check if pdoc is installed
if ! command -v pdoc &> /dev/null; then
    echo "pdoc is not installed. Please install it with: pip install pdoc"
    exit 1
fi

if [ ! -d "packages/railtracks/src/railtracks" ]; then
    echo "Source directory packages/railtracks/src/railtracks not found"
    exit 1
fi

mkdir -p docs/api_reference

echo "Running pdoc to generate API documentation..."
pdoc packages/railtracks/src/railtracks \
    --output-dir docs/api_reference \
    -d google \
    --include-undocumented \
    --logo https://raw.githubusercontent.com/RailtownAI/railtracks/main/docs/assets/logo.svg \
    # -t pdoc

echo "API documentation generated successfully in docs/api_reference/"
