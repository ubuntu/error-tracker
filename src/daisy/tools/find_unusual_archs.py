#!/usr/bin/python
import pycassa
from daisy import config
from collections import Counter, defaultdict
from pycassa.cassandra.ttypes import NotFoundException
import sys
from datetime import datetime, timedelta
from multiprocessing.pool import ThreadPool
import json
import urllib
from datetime import datetime, timedelta
from hashlib import sha1
import time

THREADS = 6

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool('crashdb', config.cassandra_hosts, timeout=1,
                              pool_size=THREADS, credentials=creds)
oops = pycassa.ColumnFamily(pool, 'OOPS')
bucket = pycassa.ColumnFamily(pool, 'Bucket')

url = ('https://errors.ubuntu.com/api/1.0/most-common-problems/'
       '?limit=100&format=json')


def get(*args, **kwargs):
    try:
        return oops.get(*args, **kwargs)
    except NotFoundException:
        return {}

def range_of_dates(base=datetime.today(), days=10):
    d = [(base - timedelta(days=x)).strftime('%Y%m%d') for x in range(0, days)]
    return d

def buckets_modified(days=10):
    cf = pycassa.ColumnFamily(pool, 'DayBucketsCount')
    for d in range_of_dates(days=days):
        return [key for key, count in cf.xget(d)
                if not key.startswith('failed:')]

def map_oopses(l):
    kwargs = {'columns': ['Architecture']}
    p = ThreadPool(THREADS)
    # TODO speed this up by using multiget with chunks
    g = lambda x: get(x, **kwargs)
    return [x['Architecture'] for x in p.map(g, l)]

def map_oopses_and_systems(l):
    kwargs = {'columns': ['Architecture', 'SystemIdentifier']}
    p = ThreadPool(THREADS)
    # TODO speed this up by using multiget with chunks
    oopses = defaultdict(int)
    systems = defaultdict(set)
    g = lambda x: get(x, **kwargs)
    for x in p.map(g, l):
        if 'Architecture' not in x or 'SystemIdentifier' not in x:
            continue
        arch = x['Architecture']
        oopses[arch] += 1
        systems[arch].add(x['SystemIdentifier'])
    return (oopses, systems)

def hash_for_bucket(bucket):
    cf = pycassa.ColumnFamily(pool, 'Hashes')
    h = sha1(bucket).hexdigest()
    try:
        cf.get('bucket_%s' % h[0], columns=[h])
        return h
    except NotFoundException:
        return bucket

def go(bucket, all_oopses):
    #print 'getting architectures for', len(all_oopses), 'OOPSes'
    if len(all_oopses) < 100:
        return False
    if 'StacktraceTop' not in oops.get(all_oopses[0]):
        return False

    m = Counter(map_oopses(all_oopses)).most_common()
    values = [v for k,v in m]
    total = float(sum(values))
    for x in values:
        if x / total >= 0.75:
            print '%s:' % hash_for_bucket(bucket)
            for k, v in m:
                print '%s: %d, %.2f' % (k, v, v / total)

            oopses, systems = map_oopses_and_systems(all_oopses)
            oopses_count = sum(oopses.values())
            systems_count = sum(len(x) for x in systems)
            all_rate = oopses_count / float(systems_count)
            print 'all rate:', all_rate
            for arch in oopses:
                rate = oopses[arch] / float(len(systems[arch]))
                print arch, 'rate:', rate, rate - all_rate
            return True

def most_common_today():
    data = urllib.urlopen(url).read()
    for obj in json.loads(data)['objects']:
        yield obj['function']

def summarize_bucket(b):
    start = datetime.utcnow() - timedelta(days=3)
    kwargs = {'column_start': start}
    start = time.time()
    all_oopses = [str(u) for u, _ in bucket.xget(b, **kwargs)]
    if go(b, all_oopses):
        took = time.time() - start
        print '(took %ds)' % took
        print

if __name__ == '__main__':
    #for b in most_common_today():
    #    summarize_bucket(b)
    for b in buckets_modified():
        summarize_bucket(b)

