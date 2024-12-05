#!/usr/bin/python

from __future__ import print_function
import pycassa
import sys
import time

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
counters_cf = pycassa.ColumnFamily(pool, 'Counters')

cols = ['Package', 'SourcePackage', 'DistroRelease']
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
    if counts > 10000:
        break
    for instance in chunks(str_instances, 3):
        oopses = oops_cf.multiget(instance, columns=cols)
        for oops in oopses:
            timestamp = oops_cf.get(oops, column_count=1, include_timestamp=True)
            timestamp = timestamp.values()[0][1]
            day_key = time.strftime('%Y%m%d', time.gmtime(timestamp / 1000000))
            # We started counting these after 12/05/2013
            if (timestamp / 1000000) > 1386201600:
                #print("Skipped one from %s" % day_key)
                continue
            data = oopses[oops]
            if Counter(cols) != Counter(data.keys()):
                continue
            release = data.get('DistroRelease')
            if not release:
                continue
            #if not release.startswith('Ubuntu') or \
            #   release in ['Ubuntu 13.10', 'Ubuntu 14.04']:
            #    continue
            if not release == 'Ubuntu 13.10':
                continue
            package = data.get('Package', '')
            if '[origin:' in package:
                continue
            version = None
            if package:
                package, version = split_package_and_version(package)
            if version == '':
                continue
            src_package = data.get('SourcePackage', '')
            if src_package == '':
                continue
            src_package, src_version = split_package_and_version(src_package)
            value = "%s:%s:%s" % (release, src_package, version)
            #print('Would insert %s = {%s, ""}' % (value, day_key))
            counters_cf.insert(value, {day_key: ''})
print_totals(force=True)
