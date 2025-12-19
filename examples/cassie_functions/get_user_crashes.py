#!/usr/bin/env python3
"""Example usage of get_user_crashes function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_user_crashes

# Setup Cassandra connection
setup_cassandra()

# Example: Get crashes for a specific user
user_token = "1bc37b6e0af2cffdbe23e49819248230b56ce9cc765abf5344f6cec44d6538741340a54c15f21a71546e9de6bb779374a98cc1aff961b54494ae5984eade39db"
limit = 20

crashes = get_user_crashes(user_token, limit=limit)
print(f"Found {len(crashes)} user crashes")
for crash_id, timestamp in crashes:
    print(f"Crash: {crash_id}, Timestamp: {timestamp}")
