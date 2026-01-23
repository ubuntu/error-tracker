#!/usr/bin/env python3
"""Example usage of get_metadata_for_buckets function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_metadata_for_buckets
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get metadata for multiple buckets
bucketids = ["bucket_1", "bucket_2", "bucket_3"]
release = "Ubuntu 24.04"

metadata_dict = get_metadata_for_buckets(bucketids, release=release)
for bucketid, metadata in metadata_dict.items():
    print(f"Bucket {bucketid}: {metadata}")
