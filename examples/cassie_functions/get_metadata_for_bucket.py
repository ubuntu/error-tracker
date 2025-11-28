#!/usr/bin/env python3
"""Example usage of get_metadata_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_metadata_for_bucket

# Example: Get metadata for a specific bucket
bucketid = "example_bucket_id_12345"
release = "Ubuntu 22.04"

metadata = get_metadata_for_bucket(bucketid, release=release)
print(f"Metadata: {metadata}")
