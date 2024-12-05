#!/usr/bin/python

import pycassa
import uuid
from daisy import config
from utils import split_package_and_version
from collections import Counter

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              max_retries=100, credentials=creds)

bucketmetadata_cf = pycassa.ColumnFamily(pool, 'BucketMetadata')
bugtocrashsignatures_cf = pycassa.ColumnFamily(pool, 'BugToCrashSignatures')

cols = ['CreatedBug']
count = 0
for bucket, data in bucketmetadata_cf.get_range(columns=cols):
    count += 1
    if count % 100000 == 0:
        print 'processed', count
    bug = int(data['CreatedBug'])
    #print('Would insert %s = {%s: ""}' % (bug, bucket))
    bugtocrashsignatures_cf.insert(bug, {bucket: ''})

print 'total processed', count
