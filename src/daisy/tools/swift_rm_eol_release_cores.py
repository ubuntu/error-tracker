#!/usr/bin/python

# iterate over the core files in swift and if they are rather old assume they
# got dropped from the amqp queue somehow and readd them after looking up the
# arch for the core file in cassandra.

import amqplib.client_0_8 as amqp
import atexit
import swiftclient
import sys

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

from daisy import config
from daisy import utils
from datetime import datetime, timedelta

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password)
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)
session.default_consistency_level = ConsistencyLevel.LOCAL_ONE

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

_cached_swift.http_conn = None
connection = amqp.Connection(host=config.amqp_host,
                             userid=config.amqp_username,
                             password=config.amqp_password)
channel = connection.channel()
atexit.register(connection.close)
atexit.register(channel.close)

now = datetime.utcnow()
abitago = now - timedelta(7)
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
    oops_lookup_stmt = session.prepare(
        "SELECT value FROM \"OOPS\" WHERE key=? and column1='DistroRelease'")
    for core in toreview:
        core_date = datetime.strptime(core['last_modified'],
                                      '%Y-%m-%dT%H:%M:%S.%f')
        uuid = core['name']
        count += 1
        # it may still be in the queue awaiting its first retrace attempt
        if core_date > abitago:
            print 'skipping too new core %s' % uuid
            continue
        # the query returns a row with only the value in it e.g.
        # Row(value=u'Ubuntu 17.10')
        release = str(session.execute(oops_lookup_stmt, [uuid])[0][0])
        # don't waste resources retrying these EoL releases
        if not utils.retraceable_release(release):
            try:
                _cached_swift.delete_object(bucket, uuid)
            except swiftclient.client.ClientException as e:
                if '404 Not Found' in str(e):
                    continue
            print >>sys.stderr, 'Removed %s core %s from swift' % \
                (release, uuid)
            unqueued_count += 1
            continue
    print('Finished, reviewed %i cores, removed %i cores.' %
          (count, unqueued_count))
