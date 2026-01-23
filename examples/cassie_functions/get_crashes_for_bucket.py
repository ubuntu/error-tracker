#!/usr/bin/env python3
"""Example usage of get_crashes_for_bucket function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_crashes_for_bucket
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get crashes for a specific bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"
limit = 10

crashes = get_crashes_for_bucket(bucketid, limit=limit)
print(f"Found {len(crashes)} crashes")
for crash in crashes:
    print(f"Crash ID: {crash}")

start_uuid = "cbb0a4b6-d120-11f0-a9ed-fa163ec8ca8c"
crashes = get_crashes_for_bucket(bucketid, limit=limit, start=start_uuid)
print(f"Found {len(crashes)} crashes (started at {start_uuid})")
for crash in crashes:
    print(f"Crash ID: {crash}")
