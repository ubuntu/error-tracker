#!/usr/bin/env python3
"""Example usage of get_user_crashes function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_user_crashes

# Example: Get crashes for a specific user
user_token = "example_user_token_12345"
limit = 20

crashes = get_user_crashes(user_token, limit=limit)
print(f"Found {len(crashes)} user crashes")
for crash_id, timestamp in crashes[:5]:
    print(f"Crash: {crash_id}, Timestamp: {timestamp}")
