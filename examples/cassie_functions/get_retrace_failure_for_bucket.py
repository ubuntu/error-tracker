#!/usr/bin/env python3
"""Example usage of get_retrace_failure_for_bucket function."""

import sys
sys.path.insert(0, '../../src')

from errortracker.cassandra import setup_cassandra
from errors.cassie import get_retrace_failure_for_bucket

# Setup Cassandra connection
setup_cassandra()

# Example: Get retrace failure information
bucketid = "failed:/usr/bin/rygel:11:i686:/usr/lib/libde265.so.0.0.8+2ddca:/usr/lib/libde265.so.0.0.8+14de2:/usr/lib/libde265.so.0.0.8+150f6:/usr/lib/libde265.so.0.0.8+1b4d2:/usr/lib/libde265.so.0.0.8+1c9ef:/usr/lib/libde265.so.0.0.8+1d5e9:/usr/lib/libde265.so.0.0.8+1d84c:/usr/lib/libde265.so.0.0.8+1d8f5:/usr/lib/libde265.so.0.0.8+1dfd1:/usr/lib/libde265.so.0.0.8+268bf:/lib/i386-linux-gnu/libpthread-2.19.so+6f70:/lib/i386-linux-gnu/libc-2.19.so+ebbee"

failure_data = get_retrace_failure_for_bucket(bucketid)
print(bucketid)
print(f"Retrace failure data: {failure_data}")


bucketid = "failed:/usr/bin/gnome-session:5:/usr/lib/x86_64-linux-gnu/libglib-2.0.so.0.8600.1+47733:/usr/lib/x86_64-linux-gnu/libglib-2.0.so.0.8600.1+47e5e:/usr/lib/x86_64-linux-gnu/libglib-2.0.so.0.8600.1+480f7:/usr/lib/x86_64-linux-gnu/libglib-2.0.so.0.8600.1+48483:/usr/bin/gnome-session+dde:/usr/lib/x86_64-linux-gnu/libc.so.6+2575:/usr/lib/x86_64-linux-gnu/libc.so.6+2628:/usr/bin/gnome-session+1155"

failure_data = get_retrace_failure_for_bucket(bucketid)
print(bucketid)
print(f"Retrace failure data: {failure_data}")
