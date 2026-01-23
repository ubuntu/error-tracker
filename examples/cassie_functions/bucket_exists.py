#!/usr/bin/env python3
"""Example usage of bucket_exists function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import bucket_exists
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Check if a bucket exists
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"

exists = bucket_exists(bucketid)
print(f"Bucket {bucketid} exists: {exists}")
