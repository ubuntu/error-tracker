#!/usr/bin/env python3
"""Example usage of get_problem_for_hash function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_problem_for_hash
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get problem bucket for a hash
hashed = "3f322b0f41718376ceefaf12fe3c69c046b6f643"

problem = get_problem_for_hash(hashed)
if problem:
    print(f"Problem bucket: {problem}")
else:
    print("No problem found for hash")
