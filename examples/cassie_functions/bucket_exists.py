#!/usr/bin/env python3
"""Example usage of bucket_exists function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import bucket_exists

# Setup Cassandra connection
setup_cassandra()

# Example: Check if a bucket exists
bucketid = "example_bucket_id_12345"

exists = bucket_exists(bucketid)
print(f"Bucket {bucketid} exists: {exists}")
