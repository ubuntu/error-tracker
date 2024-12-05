#!/usr/bin/python2.7

import sys
import pycassa
import datetime
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

dayusers_cf = pycassa.ColumnFamily(pool, 'DayUsers')

# Utilities

def _date_range_iterator(start, finish):
    # Iterate all the values including and between the start and finish date
    # string.
    while start <= finish:
        yield start.strftime('%Y%m%d')
        start += datetime.timedelta(days=1)

# Main
if __name__ == '__main__':
    if len(sys.argv) > 2:
        start = datetime.datetime.strptime(sys.argv[1], '%Y%m%d')
        end = datetime.datetime.strptime(sys.argv[2], '%Y%m%d')
        i = _date_range_iterator(start, end)
    else:
        today = datetime.date.today()
        i = _date_range_iterator(today - datetime.timedelta(days=10), today)
    releases = ['16.04', '18.04', '20.04',
                '21.10', '22.04']
    header = "Date    , "
    for release in releases:
        header += '%s, ' % release
    header += 'Total'
    print('%s' % header)
    for date in i:
        counts = []
        total = 0
        for release in releases:
            count = dayusers_cf.get_count('Ubuntu %s:%s' % (release, date))
            counts.append(str(count))
            total += count
        print('%s, %s, %s' % (date, ', '.join(counts), total))
