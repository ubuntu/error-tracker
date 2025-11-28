#!/usr/bin/env python3
"""Example usage of get_versions_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_versions_for_bucket

# Example: Get versions for a bucket
bucketid = "example_bucket_id_12345"

versions = get_versions_for_bucket(bucketid)
print(f"Versions: {versions}")
for version, count in list(versions.items())[:5]:
    print(f"Version: {version}, Count: {count}")
