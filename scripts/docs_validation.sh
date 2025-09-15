#!/bin/bash

# Script to validate that all documentation scripts in docs/scripts/ can execute successfully

set -e  # Exit on any error

echo "Starting documentation scripts validation..."

# Check if we're in the right directory
if [ ! -d "docs/scripts" ]; then
    echo "Error: docs/scripts directory not found!"
    exit 1
fi

# Check if API keys are set (optional - scripts might work without them)
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY not set"
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Warning: ANTHROPIC_API_KEY not set"
fi

if [ -z "$HF_TOKEN" ]; then
    echo "Warning: HF_TOKEN not set"
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY not set"
fi


# Initialize counters
total_scripts=0
successful_scripts=0
failed_scripts=0

# Find all Python scripts in docs/scripts/
for script in docs/scripts/*.py; do
    # ======= remove when #673 is completed =======
    # Skip tools_mcp_guides.py since it requires privileged env setup (Temporary) 
    if [[ "$(basename "$script")" == "tools_mcp_guides.py" ]]; then
        echo ""
        echo "Skipping: $script (requires MCP environment variables)"
        echo "---"
        continue
    fi
    # =============================================

    if [ -f "$script" ]; then
        total_scripts=$((total_scripts + 1))
        echo ""
        echo "Executing: $script"
        echo "---"
        
        if python "$script"; then
            echo "Successfully executed: $script"
            successful_scripts=$((successful_scripts + 1))
        else
            echo "Failed to execute: $script"
            failed_scripts=$((failed_scripts + 1))
        fi
        echo "---"
    fi
done

# Summary
echo ""
echo "SUMMARY"
echo "================================================"
echo "Total scripts found: $total_scripts"
echo "Successful: $successful_scripts"
echo "Failed: $failed_scripts"

if [ $failed_scripts -eq 0 ]; then
    echo ""
    echo "All documentation scripts executed successfully!"
    exit 0
else
    echo ""
    echo "some documentation scripts failed!"
    exit 1
fi
