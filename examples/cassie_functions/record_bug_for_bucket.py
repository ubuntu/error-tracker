#!/usr/bin/env python3
"""Example usage of record_bug_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import record_bug_for_bucket

# Setup Cassandra connection
setup_cassandra()

# Example: Record a bug for a bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"
bug = 123456  # Launchpad bug number

record_bug_for_bucket(bucketid, bug)
print(f"Recorded bug {bug} for bucket {bucketid}")
