#!/usr/bin/env python3
"""Example usage of get_system_image_versions function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_system_image_versions
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get versions for a system image type
image_type = "device_image"

versions = get_system_image_versions(image_type)
if versions:
    print(f"Found {len(versions)} versions")
    for version in versions:
        print(f"Version: {version}")
else:
    print("No versions found")
