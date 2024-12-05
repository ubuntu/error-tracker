#!/usr/bin/python

import sys
import pycassa
from pycassa.cassandra.ttypes import NotFoundException
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              max_retries=100, credentials=creds)

bucket_cf = pycassa.ColumnFamily(pool, 'Bucket')
buckets_cf = pycassa.ColumnFamily(pool, 'Buckets')

from itertools import izip_longest
def grouper(iterable, n):
    args = [iter(iterable)] * n
    return izip_longest(*args)

row_count = 0
dry_run = '--dry-run' in sys.argv

new_count = 0
for k,v in buckets_cf.get_range():
    row_count += 1
    try:
        bucket_cf.get(k, column_count=1)
        continue
    except NotFoundException:
        new_count += 1
    for group in grouper(v, 100):
        # If the list isn't evenly divisible, we'll end up with a final
        # chunk with None values on the end.
        gen = ((pycassa.util.uuid.UUID(x),'') for x in group if x)
        o = pycassa.util.OrderedDict(gen)
        if not dry_run:
            bucket_cf.insert(k, o)
    if row_count % 100000 == 0:
        print 'Copied', row_count, 'rows', '(%d new).' % new_count
