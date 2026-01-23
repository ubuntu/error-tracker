#!/usr/bin/env python3
"""Example usage of get_crash_count function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_crash_count
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get crash count for Ubuntu 24.04
start = 3
finish = 10
release = "Ubuntu 24.04"

for date, count in get_crash_count(start, finish, release=release):
    print(f"Date: {date}, Release: {release}, Crashes: {count}")

for date, count in get_crash_count(start, finish):
    print(f"Date: {date}, Crashes: {count}")
