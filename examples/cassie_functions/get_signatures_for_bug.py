#!/usr/bin/env python3
"""Example usage of get_signatures_for_bug function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_signatures_for_bug

# Setup Cassandra connection
setup_cassandra()

# Example: Get crash signatures for a bug
bug = 2066094  # Launchpad bug number

signatures = get_signatures_for_bug(bug)
print(f"Found {len(signatures)} signatures")
for signature in signatures:
    print(f"Signature: {signature}")

bug = 1578412  # Launchpad bug number

signatures = get_signatures_for_bug(bug)
print(f"Found {len(signatures)} signatures")
for signature in signatures:
    print(f"Signature: {signature}")
