#!/usr/bin/env python3
"""Example usage of get_problem_for_hash function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_problem_for_hash

# Setup Cassandra connection
setup_cassandra()

# Example: Get problem bucket for a hash
hashed = "abc123def456"

problem = get_problem_for_hash(hashed)
if problem:
    print(f"Problem bucket: {problem}")
else:
    print("No problem found for hash")
