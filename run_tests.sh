#!/bin/bash
# Run tests with custom test runner that handles schemathesis compatibility

# Activate virtual environment
source venv/bin/activate

# Run the custom test runner
python patches/custom_test_runner.py "$@"
