#!/usr/bin/env python3
"""Example usage of get_average_instances function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_average_instances

# Setup Cassandra connection
setup_cassandra()

# Example: Get average instances for a bucket
bucketid = "example_bucket_id_12345"
release = "Ubuntu 24.04"
days = 7

for timestamp, avg in get_average_instances(bucketid, release, days=days):
    print(f"Timestamp: {timestamp}, Average: {avg}")
