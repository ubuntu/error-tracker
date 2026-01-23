#!/usr/bin/env python3
"""Example usage of get_traceback_for_bucket function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_traceback_for_bucket
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get traceback for a bucket
bucketid = "/usr/bin/classicmenu-indicator:AttributeError:/usr/bin/classicmenu-indicator@11:main:__init__"

traceback = get_traceback_for_bucket(bucketid)
if traceback:
    print(f"Traceback: {traceback}...")
else:
    print("No traceback found")
