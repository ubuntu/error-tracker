#!/usr/bin/env python3
"""Example usage of get_versions_for_bucket function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_versions_for_bucket
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get versions for a bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"

versions = get_versions_for_bucket(bucketid)
print(f"Versions: {versions}")
for os, version in list(versions.items()):
    print(f"OS: {os}, Version: {version}")
