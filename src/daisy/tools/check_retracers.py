#!/usr/bin/python

import datetime
import os
import sys
import pycassa
from pycassa.cassandra.ttypes import NotFoundException
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)
# this CF doesn't contain any data
ttr = pycassa.ColumnFamily(pool, 'TimeToRetrace')

# Main

def main():
    # this file is created by retracer_status.py
    if not os.path.isfile('/tmp/retracer-status.txt'):
        print('/tmp/retracer-status.txt not found')
        sys.exit(1)
    with open('/tmp/retracer-status.txt', 'r') as f:
        for line in f.readlines():
            if line.strip() == "status=retracing":
                sys.exit(0)
            elif line.strip() == "status=stopped":
                sys.exit(2)
    sys.exit(2)

    #l = [v for k, v in ttr.xget(date)]
    #count = len(l)
    #if count > 0:
    #    m = sum(l) / count
    #    if m > config.time_to_retrace_alert:
    #        print 'Retracers are taking too long to process:'
    #        msg = 'Currently: %d. Maximum: %d (config.time_to_retrace_alert)'
    #        print msg % (m, config.time_to_retrace_alert)
    #        # Nagios uses exit code 1 for WARNING and 2 for CRITICAL.
    #        sys.exit(2)

if __name__ == '__main__':
    main()
