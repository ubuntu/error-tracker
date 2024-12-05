#!/usr/bin/python

from __future__ import print_function
import pycassa
import sys

from daisy import config
from daisy.utils import split_package_and_version
from collections import Counter

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              max_retries=100, credentials=creds)

oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
bucket_cf = pycassa.ColumnFamily(pool, 'Bucket')
bucketversionsystems_cf = pycassa.ColumnFamily(pool, 'BucketVersionSystems2')

cols = ['SystemIdentifier', 'Package']
counts = 0

wait_amount = 30000000
wait = wait_amount
start = pycassa.columnfamily.gm_timestamp()

def print_totals(force=False):
    global wait
    if force or (pycassa.columnfamily.gm_timestamp() - start > wait):
        wait += wait_amount
        r = (float(counts) / (pycassa.columnfamily.gm_timestamp() - start) * 1000000 * 60)
        print('Processed:', counts, '(%d/min)' % r, sep='\t')
        print
        sys.stdout.flush()

def chunks(l, n):
    # http://stackoverflow.com/a/312464/190597
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def to_utf8(string):
    if type(string) == unicode:
        string = string.encode('utf-8')
    return string

for bucket, instances in bucket_cf.get_range(include_timestamp=True,
        buffer_size=2*1024):
    print_totals()
    str_instances = [str(instance) for instance in instances]
    counts += 1
    #if counts > 1000:
    #    break
    # keep track of (system, version) as we only want to count each system once
    # per version
    insertions = []
    for instance in chunks(str_instances, 3):
        oopses = oops_cf.multiget(instance, columns=cols)
        for oops in oopses:
            data = oopses[oops]
            if Counter(cols) != Counter(data.keys()):
                continue
            system = data.get('SystemIdentifier')
            package = data.get('Package', '')
            version = None
            if package:
                package, version = split_package_and_version(package)
            if version == '':
                continue
            if (system, version) in insertions:
                continue
            key = (to_utf8(bucket), to_utf8(version))
            #print('Would insert %s = {%s, ""}' % (key, to_utf8(system)))
            insertions.append((system, version))
            bucketversionsystems_cf.insert(key, {system: ''})
print_totals(force=True)
