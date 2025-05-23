#!/bin/bash
# Run tests with simplified test runner that bypasses schemathesis

# Activate virtual environment
source venv/bin/activate

# Run the simplified test runner
python patches/simplified_test_runner.py "$@"
