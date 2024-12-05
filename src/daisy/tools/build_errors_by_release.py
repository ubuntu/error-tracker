#!/usr/bin/python

import datetime
import pycassa
import uuid
from pycassa.cassandra.ttypes import NotFoundException
from daisy import config
from daisy.metrics import VerboseListener
from collections import Counter
import argparse
import sys
import time

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=10,
                              listeners=[VerboseListener()],
                              # Will retry for up to three hours.
                              max_retries=20, credentials=creds)

oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
firsterror = None
errorsbyrelease = None
systems = None

columns = ['SystemIdentifier', 'DistroRelease']
kwargs = {
    # 10k is too much. jumbee ran out of memory trying to handle too many runs
    # of this.
    # Knocking down to 1K from 5 to give the cluster a bit more breathing room.
    'buffer_size': 1024,
    'include_timestamp': True,
    'columns': columns,
}

def main(verbose=False):
    started = time.time()
    r = ['Ubuntu 12.04', 'Ubuntu 12.10', 'Ubuntu 13.04', 'Ubuntu 13.10']
    stored = {}
    for release in r:
        stored[release] = {k:v for k,v in firsterror.xget(release)}
    for release in r:
        print release, len(stored[release])
        sys.stdout.flush()
    print 'generating FirstError took', time.time() - started, 'seconds.'

    started = time.time()
    count = 0
    for key, oops in oops_cf.get_range(**kwargs):
        if verbose:
            count += 1
            if count % 10000 == 0:
                print 'processed', count
                print float(count) / (time.time() - started), '/ s'
                sys.stdout.flush()

        if Counter(columns) != Counter(oops.keys()):
            continue

        # Some bogus release names, like that of
        # 146104fadced68c9dedfd124427b7e05d62511b3c79743dd7b63465bb090f472
        # a6a5b34f32f8ac120ac47003f2a9f08030d368427cdf161cfa9ebad2ec8044bd
        release = oops['DistroRelease'][0].encode('utf8')
        if len(release) > 2048 or '\n' in release:
            # Bogus data.
            continue
        system_token = oops['SystemIdentifier'][0]

        if release not in r:
            continue

        occurred = oops['DistroRelease'][1] / 1000000
        occurred = datetime.datetime.fromtimestamp(occurred)
        occurred = occurred.replace(hour=0, minute=0, second=0, microsecond=0)

        first_error_date = None
        try:
            first_error_date = stored[release][system_token]
        except KeyError:
            pass
        #try:
        #    first_error_date = firsterror.get(release, columns=[system_token])
        #    first_error_date = first_error_date[system_token]
        #except NotFoundException:
        #    pass

        if not first_error_date or first_error_date > occurred:
            firsterror.insert(release, {system_token: occurred})
            stored[release][system_token] = occurred
            first_error_date = occurred

        oops_id = uuid.UUID(key)
        errorsbyrelease.insert((release, occurred), {oops_id: first_error_date})
        # We want to measure just the systems that have reported a
        # DistroRelease field and are running an official Ubuntu release.
        systems.insert((release, occurred), {system_token: ''})

    if verbose:
        print 'total processed', count

def parse_options():
    parser = argparse.ArgumentParser(
                description='Back-populate ErrorsByRelease and FirstError.')
    parser.add_argument('--write-hosts', nargs='+',
                        help='Cassandra host and IP (colon-separated) to write'
                        ' results to.')
    return parser.parse_args()

if __name__ == '__main__':
    options = parse_options()
    if options.write_hosts:
        write_pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                                            options.write_hosts, timeout=60,
                                            pool_size=15, max_retries=100,
                                            credentials=creds)
        firsterror = pycassa.ColumnFamily(write_pool, 'FirstError')
        errorsbyrelease = pycassa.ColumnFamily(write_pool, 'ErrorsByRelease')
        systems = pycassa.ColumnFamily(write_pool, 'SystemsForErrorsByRelease')

    main(True)
 
