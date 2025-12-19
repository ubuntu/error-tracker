#!/usr/bin/env python3
"""Example usage of get_bucket_counts function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_bucket_counts

# Setup Cassandra connection
setup_cassandra()

# Example: Get bucket counts for Ubuntu 24.04 today
print("Ubuntu 24.04 - today")
result = get_bucket_counts(
    release="Ubuntu 24.04",
    period="today"
)

print(f"Found {len(result)} buckets")
for bucket, count in result[:30]:
    print(f"Bucket: {bucket}, Count: {count}")
# Example: Get bucket counts for Ubuntu 24.04 today

print("Past week")
result = get_bucket_counts(
    period="week"
)

print(f"Found {len(result)} buckets")
for bucket, count in result[:30]:
    print(f"Bucket: {bucket}, Count: {count}")

print("Past month")
result = get_bucket_counts(
    period="month"
)

print(f"Found {len(result)} buckets")
for bucket, count in result[:30]:
    print(f"Bucket: {bucket}, Count: {count}")

print("Nautilus package - today")
result = get_bucket_counts(
    period="today",
    package="nautilus",
)

print(f"Found {len(result)} buckets")
for bucket, count in result[:30]:
    print(f"Bucket: {bucket}, Count: {count}")
