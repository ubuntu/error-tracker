#!/usr/bin/env python3
"""Example usage of get_average_instances function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_average_instances

# Example: Get average instances for a bucket
bucketid = "example_bucket_id_12345"
release = "Ubuntu 22.04"
days = 7

for timestamp, avg in get_average_instances(bucketid, release, days=days):
    print(f"Timestamp: {timestamp}, Average: {avg}")
