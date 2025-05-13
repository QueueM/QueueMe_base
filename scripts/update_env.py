#!/usr/bin/env python3
"""
Environment Variable Update Utility

This script updates the .env file with new values or adds them if they don't exist.
It preserves existing values and comments.

Usage:
    python scripts/update_env.py KEY=VALUE [KEY2=VALUE2 ...]

Example:
    python scripts/update_env.py USE_CONNECTION_POOLING=true DB_POOL_SIZE=20
"""

import os
import re
import sys
from pathlib import Path


def update_env_file(env_file, updates):
    """
    Update .env file with new key-value pairs

    Args:
        env_file: Path to the .env file
        updates: Dictionary of key-value pairs to update or add
    """
    if not os.path.exists(env_file):
        print(f"Error: {env_file} not found")
        return False

    # Read current content
    with open(env_file, "r") as f:
        lines = f.readlines()

    # Track which keys have been updated
    updated_keys = set()
    modified_lines = []

    # Process each line
    for line in lines:
        # Skip comments and empty lines
        if line.strip() == "" or line.strip().startswith("#"):
            modified_lines.append(line)
            continue

        # Check if this line contains a key that needs updating
        match = re.match(r"^([A-Za-z0-9_]+)=(.*)$", line.strip())
        if match:
            key, current_value = match.groups()
            if key in updates:
                # Update the line with new value
                modified_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                # Keep the line as is
                modified_lines.append(line)
        else:
            # Keep non-key-value lines as is
            modified_lines.append(line)

    # Add new keys that weren't found in the file
    new_keys = set(updates.keys()) - updated_keys
    if new_keys:
        modified_lines.append("\n# Added by update_env.py\n")
        for key in new_keys:
            modified_lines.append(f"{key}={updates[key]}\n")

    # Write updated content back to file
    with open(env_file, "w") as f:
        f.writelines(modified_lines)

    print(
        f"Updated {len(updated_keys)} existing keys and added {len(new_keys)} new keys to {env_file}"
    )
    return True


def main():
    """Main function to parse arguments and update .env file"""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} KEY=VALUE [KEY2=VALUE2 ...]")
        return False

    # Get the .env file path
    base_dir = Path(__file__).resolve().parent.parent
    env_file = os.path.join(base_dir, ".env")

    # Parse key-value pairs from arguments
    updates = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            updates[key] = value
        else:
            print(f"Invalid argument format: {arg}. Expected KEY=VALUE")

    return update_env_file(env_file, updates)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
