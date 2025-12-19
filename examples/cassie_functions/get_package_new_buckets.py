#!/usr/bin/env python3
"""Example usage of get_package_new_buckets function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_package_new_buckets

# Setup Cassandra connection
setup_cassandra()

# Example: Get new buckets for a package version
src_pkg = "zsh"
previous_version = "5.8-5"
new_version = "5.9-4"

new_buckets = get_package_new_buckets(src_pkg, previous_version, new_version)
print(f"Found {len(new_buckets)} new buckets")
for bucket in new_buckets:
    print(f"Bucket: {bucket}")

src_pkg = "ubuntu-drivers-common"
previous_version = "1:0.9.6.2~0.22.04.8"
new_version = "1:0.9.6.2~0.22.04.10"

new_buckets = get_package_new_buckets(src_pkg, previous_version, new_version)
print(f"Found {len(new_buckets)} new buckets")
for bucket in new_buckets:
    print(f"Bucket: {bucket}")
