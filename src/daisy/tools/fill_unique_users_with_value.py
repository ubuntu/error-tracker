#!/usr/bin/python

import sys
import pycassa
import datetime
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

uniqueusers_cf = pycassa.ColumnFamily(pool, 'UniqueUsers90Days')

# Utilities

def _date_range_iterator(start, finish):
    # Iterate all the values including and between the start and finish date
    # string.
    while start <= finish:
        yield start.strftime('%Y%m%d')
        start += datetime.timedelta(days=1)

# Main

if __name__ == '__main__':
    if len(sys.argv) > 3:
        start = datetime.datetime.strptime(sys.argv[1], '%Y%m%d')
        end = datetime.datetime.strptime(sys.argv[2], '%Y%m%d')
        value = int(sys.argv[3])
        i = _date_range_iterator(start, end)
    else:
        print 'usage: <start> <finish> <value>'
        sys.exit(1)
    for date in i:
        uniqueusers_cf.insert('Ubuntu 12.04', {date: value})
