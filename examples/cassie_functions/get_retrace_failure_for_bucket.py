#!/usr/bin/env python3
"""Example usage of get_retrace_failure_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_retrace_failure_for_bucket

# Example: Get retrace failure information
bucketid = "example_bucket_id_12345"

failure_data = get_retrace_failure_for_bucket(bucketid)
print(f"Retrace failure data: {failure_data}")
