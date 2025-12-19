#!/usr/bin/env python3
"""Example usage of get_retracer_counts function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_retracer_counts

# Setup Cassandra connection
setup_cassandra()

# Example: Get retracer counts for a date range
start = 0
finish = 7

for date, counts in get_retracer_counts(start, finish):
    print(f"Date: {date}")
    print(f"Counts: {counts}")
