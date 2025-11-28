#!/usr/bin/env python3
"""Example usage of get_signatures_for_bug function."""

import sys
sys.path.insert(0, '../../src')

from errors.cassie import get_signatures_for_bug

# Example: Get crash signatures for a bug
bug = 123456  # Launchpad bug number

signatures = get_signatures_for_bug(bug)
print(f"Found {len(signatures)} signatures")
for signature in signatures[:5]:
    print(f"Signature: {signature}")
