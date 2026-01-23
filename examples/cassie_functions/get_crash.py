#!/usr/bin/env python3
"""Example usage of get_crash function."""

import sys

sys.path.insert(0, "../../src")

from errors.cassie import get_crash
from errortracker.cassandra import setup_cassandra

# Setup Cassandra connection
setup_cassandra()

# Example: Get crash details
oopsid = "e3855456-cecb-11f0-b91f-fa163ec44ecd"
columns = ["Package", "StacktraceAddressSignature"]

crash_data = get_crash(oopsid, columns=columns)
print(f"Crash data: {crash_data}")
