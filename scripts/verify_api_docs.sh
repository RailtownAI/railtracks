#!/bin/bash

# RailTracks API Documentation Verification Script

set -e  # Exit on any error

if ! git diff --quiet docs/api_reference/; then
echo "API documentation is out of date!"
echo "The following files have changes:"

echo "Please run './scripts/generate_api_docs.sh' locally and commit the updated documentation."
echo "This ensures the API reference stays in sync with code changes."
exit 1
else
echo "API documentation is up to date"
fi