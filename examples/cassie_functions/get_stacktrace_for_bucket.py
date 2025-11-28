#!/usr/bin/env python3
"""Example usage of get_stacktrace_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_stacktrace_for_bucket

# Example: Get stacktrace for a bucket
bucketid = "example_bucket_id_12345"

stacktrace, thread_stacktrace = get_stacktrace_for_bucket(bucketid)
if stacktrace:
    print(f"Stacktrace: {stacktrace[:200]}...")
if thread_stacktrace:
    print(f"Thread Stacktrace: {thread_stacktrace[:200]}...")
