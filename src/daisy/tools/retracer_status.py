#!/usr/bin/python

import pycassa
from pycassa.cassandra.ttypes import NotFoundException
import datetime
import sys
from time import sleep
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

retracestats_cf = pycassa.ColumnFamily(pool, 'RetraceStats')

def main():
    # check to see if the retracing counts are changing
    date = datetime.date.today().strftime('%Y%m%d')
    try:
        previous_stats = retracestats_cf.get(date)
    # this could happen at the start of the day
    except NotFoundException:
        previous_stats = ''
        pass
    sleep(180)
    try:
        current_stats = retracestats_cf.get(date)
    # if we can't find any current stats after waiting then the retracers must
    # not be working
    except NotFoundException:
        print("status=stopped")
        sys.exit(0)
    # if the stats are the same then the retracers must not be working
    if previous_stats == current_stats:
        print('status=stopped')
    else:
        print('status=retracing')

if __name__ == '__main__':
    main()
