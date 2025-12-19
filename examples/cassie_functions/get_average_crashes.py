#!/usr/bin/env python3
"""Example usage of get_average_crashes function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_average_crashes

# Setup Cassandra connection
setup_cassandra()

# Example: Get average crashes per user
field = "zsh:5.9-6ubuntu2"
release = "Ubuntu 24.04"
days = 14

data = get_average_crashes(field, release, days=days)
print(f"Average crash data: {data}")
for timestamp, avg in data:
    print(f"Timestamp: {timestamp}, Average: {avg}")
