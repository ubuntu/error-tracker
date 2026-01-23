#!/usr/bin/env python3
"""Example usage of get_metadata_for_bucket function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_metadata_for_bucket
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get metadata for a specific bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"
release = "Ubuntu 24.04"

metadata = get_metadata_for_bucket(bucketid, release=release)
print(f"Metadata: {metadata}")
