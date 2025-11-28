#!/usr/bin/env python3
"""Example usage of get_source_package_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_source_package_for_bucket

# Setup Cassandra connection
setup_cassandra()

# Example: Get source package for a bucket
bucketid = "example_bucket_id_12345"

source_package = get_source_package_for_bucket(bucketid)
print(f"Source package: {source_package}")
