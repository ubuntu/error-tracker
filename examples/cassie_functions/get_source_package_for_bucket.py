#!/usr/bin/env python3
"""Example usage of get_source_package_for_bucket function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_source_package_for_bucket
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get source package for a bucket
bucketid = "/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread"

source_package = get_source_package_for_bucket(bucketid)
print(f"Source package: {source_package}")

bucketid = "/usr/bin/mousepad:7:mousepad_file_encoding_read_bom:mousepad_file_open:mousepad_window_open_file:mousepad_window_open_files:mousepad_application_new_window_with_files"

source_package = get_source_package_for_bucket(bucketid)
print(f"Source package: {source_package}")
