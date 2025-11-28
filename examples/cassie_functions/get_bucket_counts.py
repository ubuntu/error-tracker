#!/usr/bin/env python3
"""Example usage of get_bucket_counts function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_bucket_counts

# Setup Cassandra connection
setup_cassandra()

# Example: Get bucket counts for Ubuntu 22.04 today
result = get_bucket_counts(
    release="Ubuntu 22.04",
    period="today"
)

print(f"Found {len(result)} buckets")
for bucket, count in result[:5]:  # Show first 5
    print(f"Bucket: {bucket}, Count: {count}")
