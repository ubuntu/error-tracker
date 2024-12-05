#!/usr/bin/python
import pycassa
from daisy import config
from hashlib import sha1

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool('crashdb', ['localhost'], timeout=10,
                              credentials=creds)
bucket_cf = pycassa.ColumnFamily(pool, 'Bucket')
hashes_cf = pycassa.ColumnFamily(pool, 'Hashes')

d = {}
count = 0
for x in bucket_cf.get_range(column_count=0, filter_empty=False):
    count += 1
    if count % 10000 == 0:
        print count
    bucketid = x[0].encode('utf-8')
    h = sha1(bucketid).hexdigest()
    k = 'bucket_%s' % h[0]
    hashes_cf.insert(k, {h: bucketid})
print count
