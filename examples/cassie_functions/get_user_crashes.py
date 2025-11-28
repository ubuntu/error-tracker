#!/usr/bin/env python3
"""Example usage of get_user_crashes function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_user_crashes

# Setup Cassandra connection
setup_cassandra()

# Example: Get crashes for a specific user
user_token = "example_user_token_12345"
limit = 20

crashes = get_user_crashes(user_token, limit=limit)
print(f"Found {len(crashes)} user crashes")
for crash_id, timestamp in crashes[:5]:
    print(f"Crash: {crash_id}, Timestamp: {timestamp}")
