#!/usr/bin/env python3
"""Example usage of get_package_crash_rate function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_package_crash_rate

# Setup Cassandra connection
setup_cassandra()

# Example: Get crash rate for a package update
release = "Ubuntu 22.04"
src_package = "firefox"
old_version = "120.0"
new_version = "121.0"
pup = 100  # Phased update percentage
date = "20231115"
absolute_uri = "https://errors.ubuntu.com"

result = get_package_crash_rate(
    release, src_package, old_version, new_version, 
    pup, date, absolute_uri, exclude_proposed=False
)
print(f"Crash rate analysis: {result}")
