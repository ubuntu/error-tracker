#!/usr/bin/env python3
"""Example usage of get_traceback_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_traceback_for_bucket

# Setup Cassandra connection
setup_cassandra()

# Example: Get traceback for a bucket
bucketid = "example_bucket_id_12345"

traceback = get_traceback_for_bucket(bucketid)
if traceback:
    print(f"Traceback: {traceback[:200]}...")  # Show first 200 chars
else:
    print("No traceback found")
