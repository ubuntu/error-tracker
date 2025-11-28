#!/usr/bin/env python3
"""Example usage of get_package_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_package_for_bucket

# Example: Get package information for a bucket
bucketid = "example_bucket_id_12345"

package, version = get_package_for_bucket(bucketid)
print(f"Package: {package}")
print(f"Version: {version}")
