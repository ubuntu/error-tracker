#!/usr/bin/python

import pycassa
import datetime
import sys
from daisy import config
from daisy.constants import RAMP_UP

def main(release, start, end, verbose=False):
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)

    creds = {'username': config.cassandra_username,
             'password': config.cassandra_password}
    pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                                  config.cassandra_hosts, timeout=600,
                                  credentials=creds)

    systems = pycassa.ColumnFamily(pool, 'SystemsForErrorsByRelease')
    uniquesys = pycassa.ColumnFamily(pool, 'UniqueSystemsForErrorsByRelease')

    while start <= end:
        target_date = start
        working_date = target_date - datetime.timedelta(days=RAMP_UP - 1)
        one_day = datetime.timedelta(days=1)

        unique = set()
        while working_date <= target_date:
            [unique.add(x) for x,y in systems.xget((release, working_date))]
            working_date += one_day
        if verbose:
            print start, len(unique)
        uniquesys.insert(release, {start: len(unique)})
        start += one_day

if __name__ == '__main__':
    release = sys.argv[1]
    if len(sys.argv) > 2:
        start = datetime.datetime.strptime(sys.argv[2], '%Y%m%d')
        end = datetime.datetime.strptime(sys.argv[3], '%Y%m%d')
    else:
        start = datetime.datetime.today() - datetime.timedelta(days=1)
        end = start
    main(release, start, end, verbose=True)
