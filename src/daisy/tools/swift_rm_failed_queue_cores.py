#!/usr/bin/python

# iterate over the core files in swift and if we have attempted to retrace
# them one time just remove them from swift.
#
# N.B. should only be used if the regular queue is really full

import atexit
import pycassa
import swiftclient
import sys

from pycassa.cassandra.ttypes import NotFoundException
from daisy import config
from daisy import utils

# get container returns a max of 10000 listings, if an integer is not given
# lets get everything not 10k.
limit = None
unlimited = False
if len(sys.argv) == 2:
    limit = int(sys.argv[1])
else:
    unlimited = True

cs = getattr(config, 'core_storage', '')
if not cs:
    log('core_storage not set.')
    sys.exit(1)

provider_data = cs['swift']
opts = {'tenant_name': provider_data['os_tenant_name'],
        'region_name': provider_data['os_region_name']}
_cached_swift = swiftclient.client.Connection(
    provider_data['os_auth_url'],
    provider_data['os_username'],
    provider_data['os_password'], os_options=opts,
    auth_version='2.0')
bucket = provider_data['bucket']

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, credentials=creds)
oops_fam = pycassa.ColumnFamily(pool, 'OOPS')

_cached_swift.http_conn = None

count = 0
unqueued_count = 0

for container in \
    _cached_swift.get_container(container=bucket,
                                limit=limit,
                                full_listing=unlimited):
    # the dict is the metadata for the container
    if isinstance(container, dict):
        continue
    if limit:
        toreview = container[:limit]
    else:
        toreview = container
    for core in toreview:
        uuid = core['name']
        count += 1
        try:
            attempts = oops_fam.get(uuid, columns=['RetraceAttempts'])['RetraceAttempts']
        except NotFoundException:
            print 'Could not find RetraceAttempts for %s' % uuid
            continue
        if int(attempts) >= 1:
            _cached_swift.delete_object(bucket, uuid)
            print 'Removed %s from swift' % uuid
            unqueued_count += 1
            continue
    print 'Finished, reviewed %i cores, removed %i cores.' % (count, unqueued_count)
