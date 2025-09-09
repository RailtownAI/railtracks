#!/bin/bash

# RailTracks API Documentation Verification Script

set -e  # Exit on any error

if ! git diff --quiet docs/api_reference/; then
echo "API documentation is out of date!"
echo "BRANCH #####"
git branch
echo "#####"
echo "The following files have changes:"
git diff --name-only docs/api_reference/ | sed 's/^/   - /'
echo ""
echo "Actual differences found:"
echo "=================================================="
git diff docs/api_reference/
echo "=================================================="
echo "Please run './scripts/generate_api_docs.sh' locally and commit the updated documentation."
echo "This ensures the API reference stays in sync with code changes."
exit 1
else
echo "API documentation is up to date"
fi