#!/usr/bin/env python3
"""Example usage of get_binary_packages_for_user function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_binary_packages_for_user

# Setup Cassandra connection
setup_cassandra()

# Example: Get binary packages for a user
user = "foundations-bugs"  # quite slow (~1m56s)
user = "xubuntu-bugs"  # way faster (~12s)

packages = get_binary_packages_for_user(user)
if packages:
    print(f"Found {len(packages)} packages")
    for package in packages:
        print(f"Package: {package}")
else:
    print("No packages found")
