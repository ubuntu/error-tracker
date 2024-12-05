#!/usr/bin/python

import sys
import pycassa
from pycassa.cassandra.ttypes import NotFoundException
import datetime
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

dayusers_cf = pycassa.ColumnFamily(pool, 'DayUsers')

def _date_range_iterator(start, finish):
    # Iterate all the values including and between the start and finish date
    # string.
    while start <= finish:
        yield start.strftime('%Y%m%d')
        start += datetime.timedelta(days=1)

# Main

if __name__ == '__main__':
    if len(sys.argv) > 1:
        start = datetime.datetime.strptime(sys.argv[1], '%Y%m%d')
    else:
        start = datetime.date.today()
    i = _date_range_iterator(start - datetime.timedelta(days=90), start)
    users = set()
    for date in i:
        start = ''
        while True:
            try:
                buf = dayusers_cf.get('Ubuntu 12.04:%s' % date, column_start=start, column_count=1000)
            except NotFoundException:
                break
            buf = buf.keys()
            start = buf[-1]
            users.update(buf)
            if len(buf) < 1000:
                break
    print 'total unique users of Ubuntu 12.04 in 90 days:', len(users)
