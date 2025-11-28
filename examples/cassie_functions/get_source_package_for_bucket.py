#!/usr/bin/env python3
"""Example usage of get_source_package_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_source_package_for_bucket

# Example: Get source package for a bucket
bucketid = "example_bucket_id_12345"

source_package = get_source_package_for_bucket(bucketid)
print(f"Source package: {source_package}")
