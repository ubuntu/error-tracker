#!/usr/bin/python

import sys
import pycassa
from pycassa.cassandra.ttypes import NotFoundException
from collections import defaultdict
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

dayoops_cf = pycassa.ColumnFamily(pool, 'DayOOPS')
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
counters_cf = pycassa.ColumnFamily(pool, 'Counters')

# Main

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print >>sys.stderr, "Usage: release_name [date]"
        sys.exit(1)
    users = set()
    start = ''
    date = sys.argv[1]
    while True:
        try:
            buf = dayoops_cf.get(date, column_start=start, column_count=1000)
        except NotFoundException:
            break
        start = buf.keys()[-1]
        buf = buf.values()
        users.update(buf)
        if len(buf) < 1000:
            break
    results = defaultdict(int)
    for uuid in users:
        try:
            data = oops_cf.get(str(uuid), columns=['ProblemType', 'DistroRelease'])
            if not data['DistroRelease'].startswith('Ubuntu '):
                continue
            key = '%s:%s' % (data['ProblemType'], data['DistroRelease'])
        except (NotFoundException, KeyError):
            # Sometimes we didn't insert the full OOPS. I have no idea why.
            #print 'could not find', uuid
            continue
        results[key] += 1
    for result in results:
        k = 'oopses:%s' % result
        try:
            v = counters_cf.get(k, columns=[date])
            print k, date, 'already exists! Skipping.', v
        except NotFoundException:
            print 'adding', k, date, results[result]
            counters_cf.add(k, date, results[result])
    print results
