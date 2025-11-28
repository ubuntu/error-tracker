#!/usr/bin/env python3
"""Example usage of get_total_buckets_by_day function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_total_buckets_by_day

# Setup Cassandra connection
setup_cassandra()

# Example: Get bucket counts for the past 7 days
start = 0
finish = 7

result = get_total_buckets_by_day(start, finish)
for date, count in result:
    print(f"Date: {date}, Count: {count}")
