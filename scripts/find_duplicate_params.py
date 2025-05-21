#!/usr/bin/env python
"""
Script to find potential duplicate parameter definitions in views.
Run from your project root directory.

Usage:
    python scripts/find_duplicate_params.py
"""

import os
import re
import sys
from pathlib import Path

# Parameters to look for (add more as needed)
PARAMS_TO_FIND = [
    "search",
    "ordering",
    "page",
    "page_size"
]

# Function to check a file for potential parameter duplications
def check_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    results = []
    
    for param in PARAMS_TO_FIND:
        # Look for parameters in swagger_auto_schema
        swagger_params = re.findall(
            fr'openapi\.Parameter\(\s*[\'"]({param})[\'"]', 
            content, 
            re.IGNORECASE
        )
        
        # Look for filter backends
        has_filter_backend = False
        if param == "search" and "SearchFilter" in content:
            has_filter_backend = True
        if param == "ordering" and "OrderingFilter" in content:
            has_filter_backend = True
            
        # If we found both manual parameter definition and filter backend
        if swagger_params and has_filter_backend:
            results.append(f"⚠️ Potential duplication of '{param}' parameter in {filepath}")
            
    return results

# Main function to scan directories
def main():
    base_dirs = [
        "api",
        "apps"
    ]
    
    all_results = []
    
    for base_dir in base_dirs:
        if not os.path.exists(base_dir):
            print(f"Directory {base_dir} not found, skipping...")
            continue
            
        for root, _, files in os.walk(base_dir):
            for filename in files:
                if filename.endswith(".py"):
                    filepath = os.path.join(root, filename)
                    results = check_file(filepath)
                    all_results.extend(results)
    
    # Print results
    if all_results:
        print(f"Found {len(all_results)} potential parameter duplications:")
        for result in all_results:
            print(result)
        return 1  # Return error code for CI/CD pipelines
    else:
        print("No potential parameter duplications found.")
        return 0
        
if __name__ == "__main__":
    sys.exit(main())
