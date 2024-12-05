#!/usr/bin/python

import uuid
import hashlib
import datetime
import random
import pycassa
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=30,
                              credentials=creds)
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
dayoops_cf = pycassa.ColumnFamily(pool, 'DayOOPS')
bucketmetadata_cf = pycassa.ColumnFamily(pool, 'BucketMetadata')

release = 'Ubuntu 12.04'
today = datetime.date.today().strftime('%Y%m%d')

# TODO truncate first.

uuids = [str(uuid.uuid1()) for x in range(100000)]
oops_batcher = oops_cf.batch()
dayoops_batcher = dayoops_cf.batch()
for k in uuids:
    ident = hashlib.sha512(str(random.random())).hexdigest()
    data = {'SystemIdentifier' : ident,
            'DistroRelease' : 'Ubuntu 12.04'}
    oops_batcher = oops_batcher.insert(k, data)
    dayoops_batcher = dayoops_batcher.insert(today, {uuid.uuid1(): k})
oops_batcher.send()
dayoops_batcher.send()

bucketmetadata_batcher = bucketmetadata_cf.batch()
for k in range(10000):
    key = hashlib.sha512(str(random.random())).hexdigest()
    v = hashlib.md5(str(random.random())).hexdigest()[:15]
    k = { 'FirstSeen' : v, 'LastSeen' : v, 'Source' : v }
    bucketmetadata_batcher.insert(key, k)

    k = { '~Ubuntu 12.10:FirstSeen' : v, '~Ubuntu 12.10:LastSeen' : v, '~Ubuntu 12.10:Source' : v }
    bucketmetadata_batcher.insert(key, k)

    k = { '~Ubuntu 12.04:FirstSeen' : v, '~Ubuntu 12.04:LastSeen' : v, '~Ubuntu 12.04:Source' : v }
    bucketmetadata_batcher.insert(key, k)
bucketmetadata_batcher.send()
