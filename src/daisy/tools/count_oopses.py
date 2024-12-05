#!/usr/bin/python
import datetime
import pycassa
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts,  timeout=10,
                              credentials=creds)
dayoops = pycassa.ColumnFamily(pool, 'DayOOPS')

def _date_range_iterator(start, finish):
    while start <= finish:
        yield start.strftime('%Y%m%d')
        start += datetime.timedelta(days=1)

if __name__ == '__main__':
    total = 0
    start = datetime.datetime.strptime('20120320', '%Y%m%d')
    finish = datetime.datetime.today()
    for date in _date_range_iterator(start, finish):
        count = dayoops.get_count(date)
        print('%s: %d' % (date, count))
        total += count
    print('total: %d' % total)
