#!/usr/bin/python
import pycassa
import time
from pycassa.cassandra.ttypes import NotFoundException
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool('crashdb', config.cassandra_hosts,
                              timeout=10, credentials=creds)
bucket = pycassa.ColumnFamily(pool, 'Bucket')
buckets = pycassa.ColumnFamily(pool, 'Buckets')

count = 0
not_found_count = 0
start = time.time()
for key, pairs in buckets.get_range(column_count=1):
    count += 1
    try:
        bucket.get(key)
    except NotFoundException:
        not_found_count +=1
    if count % 10000 == 0:
        p = (not_found_count / float(count)) * 100.0
        print '%d processed, %d not found'  % (count, not_found_count),
        print '(%0.2f%%)' % p,
        elapsed = time.time() - start
        print 'at %d/s' % int(count / elapsed)
print count

# Thursday, March 7th 2013 16:00 UTC
# 1340000 processed, 50505 not found (3.77%) at 269/s
# 1340460
