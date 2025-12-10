#!/usr/bin/env python3
"""Example usage of get_package_new_buckets function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_package_new_buckets

# Setup Cassandra connection
setup_cassandra()

# Example: Get new buckets for a package version
src_pkg = "firefox"
previous_version = "120.0"
new_version = "121.0"

new_buckets = get_package_new_buckets(src_pkg, previous_version, new_version)
print(f"Found {len(new_buckets)} new buckets")
for bucket in new_buckets[:5]:
    print(f"Bucket: {bucket}")
