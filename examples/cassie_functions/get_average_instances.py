#!/usr/bin/env python3
"""Example usage of get_average_instances function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_average_instances
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get average instances for a bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"
release = "Ubuntu 24.04"
days = 7

for timestamp, avg in get_average_instances(bucketid, release, days=days):
    print(f"Timestamp: {timestamp}, Average: {avg}")
