#!/usr/bin/python

import sys
import time
import pycassa
from pycassa.cassandra.ttypes import NotFoundException
import datetime
import itertools
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

dayoops_cf = pycassa.ColumnFamily(pool, 'DayOOPS')
dayusers_cf = pycassa.ColumnFamily(pool, 'DayUsers')
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')

# Utilities

class Timer(object):
    def __init__(self, name=None):
        self.name = name
    
    def __enter__(self):
        self.tstart = time.time()
        
    def __exit__(self, type, value, traceback):
        if self.name:            
            print '[%s]' % self.name,
        print 'Elapsed: %s' % (time.time() - self.tstart)

def _date_range_iterator(start, finish):
    # Iterate all the values including and between the start and finish date
    # string.
    while start <= finish:
        yield start.strftime('%Y%m%d')
        start += datetime.timedelta(days=1)

# Main

def fetch_oopses(date):
    oopses = []
    start = pycassa.util.convert_time_to_uuid(0)
    while True:
        try:
            buf = dayoops_cf.get(date, column_start=start, column_count=500)
        except NotFoundException:
            break
        start = buf.keys()[-1]
        buf = buf.values()
        oopses.extend(buf)
        if len(buf) < 500:
            break
    return oopses

def fetch_identifiers(oopses, release):
    kwargs = dict(
        columns=['DistroRelease', 'SystemIdentifier'],
        # 30 is too high. Webops paged.
        buffer_size=5,
        read_consistency_level=pycassa.ConsistencyLevel.LOCAL_QUORUM
    )
    # The buffer size here needs to be carefully tuned. If set too high, it
    # will greatly overwhelm Cassandra. Watch nodetool closely when modifying.
    gen = ((d['SystemIdentifier'], '')
            for d in oops_cf.multiget(oopses, **kwargs).values()
                if 'SystemIdentifier' in d
                    and d.get('DistroRelease', '') == release)
    return gen

if __name__ == '__main__':
    if len(sys.argv) > 2:
        start = datetime.datetime.strptime(sys.argv[1], '%Y%m%d')
        end = datetime.datetime.strptime(sys.argv[2], '%Y%m%d')
        i = _date_range_iterator(start, end)
    else:
        today = datetime.date.today()
        i = _date_range_iterator(today - datetime.timedelta(days=90), today)
    if len(sys.argv) > 3:
        release = sys.argv[3]
    else:
        release = 'Ubuntu 12.04'

    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print 'dry run'

    for date in i:
        print 'looking up', date

        with Timer('fetching oopses'):
            oopses = fetch_oopses(date)
        print 'oopses:', len(oopses)

        if not oopses:
            continue

        with Timer('fetching identifiers'):
            ids = fetch_identifiers(oopses, release)

        with Timer('inserting identifiers'):
            # I played around with inserting all ~10K at once, but that was too
            # much overhead and it never succeeded. As said on the Cassandra
            # ML:
            # "There is a fair amount of overhead in the Thrift structures for
            # columns and mutations, so that's a pretty large mutation. In
            # general, you'll see better performance inserting many small batch
            # mutations in parallel."
            if dry_run:
                print release, date
                c = 0
            args = [iter(ids)] * 200
            for k in itertools.izip_longest(ids):
                if not dry_run:
                    dayusers_cf.insert('%s:%s' % (release, date),
                                       pycassa.util.OrderedDict(k))
                else:
                    c += len(k)
            if dry_run:
                print c
        print
