#!/usr/bin/env python3
"""Example usage of get_crashes_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_crashes_for_bucket

# Setup Cassandra connection
setup_cassandra()

# Example: Get crashes for a specific bucket
bucketid = "example_bucket_id_12345"
limit = 10

crashes = get_crashes_for_bucket(bucketid, limit=limit)
print(f"Found {len(crashes)} crashes")
for crash in crashes:
    print(f"Crash ID: {crash}")
