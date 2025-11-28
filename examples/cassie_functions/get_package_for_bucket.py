#!/usr/bin/env python3
"""Example usage of get_package_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_package_for_bucket

# Setup Cassandra connection
setup_cassandra()

# Example: Get package information for a bucket
bucketid = "example_bucket_id_12345"

package, version = get_package_for_bucket(bucketid)
print(f"Package: {package}")
print(f"Version: {version}")
