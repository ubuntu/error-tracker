#!/usr/bin/env python3
"""Example usage of get_retracer_count function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_retracer_count
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get retracer count for a specific date
date = "20260115"

count_data = get_retracer_count(date)
print(f"Retracer count data: {count_data}")
