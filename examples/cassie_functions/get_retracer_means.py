#!/usr/bin/env python3
"""Example usage of get_retracer_means function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_retracer_means

# Example: Get retracer means for date range
start = 0
finish = 7

for date, means in get_retracer_means(start, finish):
    print(f"Date: {date}")
    print(f"Means: {means}")
    break  # Show first result only
