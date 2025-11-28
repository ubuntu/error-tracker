#!/usr/bin/env python3
"""Example usage of get_crash function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_crash

# Example: Get crash details
oopsid = "example_oops_id_12345"
columns = ["Package", "StacktraceAddressSignature"]

crash_data = get_crash(oopsid, columns=columns)
print(f"Crash data: {crash_data}")
