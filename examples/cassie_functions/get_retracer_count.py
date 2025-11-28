#!/usr/bin/env python3
"""Example usage of get_retracer_count function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_retracer_count

# Setup Cassandra connection
setup_cassandra()

# Example: Get retracer count for a specific date
date = "20231115"

count_data = get_retracer_count(date)
print(f"Retracer count data: {count_data}")
