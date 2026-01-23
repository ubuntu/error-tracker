#!/usr/bin/env python3
"""Example usage of get_stacktrace_for_bucket function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_stacktrace_for_bucket
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get stacktrace for a bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"

print(bucketid)
stacktrace, thread_stacktrace = get_stacktrace_for_bucket(bucketid)
if stacktrace:
    print(f"Stacktrace: {stacktrace[:200]}...")
if thread_stacktrace:
    print(f"Thread Stacktrace: {thread_stacktrace[:200]}...")

print()

bucketid = "/usr/bin/mousepad:7:mousepad_file_encoding_read_bom:mousepad_file_open:mousepad_window_open_file:mousepad_window_open_files:mousepad_application_new_window_with_files"

print(bucketid)
stacktrace, thread_stacktrace = get_stacktrace_for_bucket(bucketid)
if stacktrace:
    print(f"Stacktrace: {stacktrace}...")
if thread_stacktrace:
    print(f"Thread Stacktrace: {thread_stacktrace}...")
