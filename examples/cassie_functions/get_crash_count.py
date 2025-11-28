#!/usr/bin/env python3
"""Example usage of get_crash_count function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_crash_count

# Example: Get crash count for Ubuntu 22.04
start = 0
finish = 7
release = "Ubuntu 22.04"

for date, count in get_crash_count(start, finish, release=release):
    print(f"Date: {date}, Crashes: {count}")
