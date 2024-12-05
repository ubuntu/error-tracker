#!/usr/bin/python

# requeue a core file that is in swift or if they do not exist in the crash
# database remove the core file from swift, a core file might be added
# to the queue an additional time but the retracer will handle that.

import amqplib.client_0_8 as amqp
import atexit
import os
import pycassa
import sys

from pycassa.cassandra.ttypes import NotFoundException
from daisy import config

if len(sys.argv) < 2:
    print >>sys.stderr, 'usage: %s <uuid>'
    sys.exit(1)

path = sys.argv[1]
uuid = os.path.basename(path)
creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, credentials=creds)
oops_fam = pycassa.ColumnFamily(pool, 'OOPS')

cs = getattr(config, 'core_storage', '')
if not cs:
    log('core_storage not set.')
    sys.exit(1)

arch = ''
try:
    arch = oops_fam.get(uuid, columns=['Architecture'])['Architecture']
except NotFoundException:
    print >>sys.stderr, 'could not find architecture for %s' % uuid
    pass
# if the Architecture can not be found the OOPS doesn't exist in the
# database so remove the core file from the swift
if arch == '':
    import swiftclient
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
    _cached_swift.delete_object(bucket, uuid)
    print >>sys.stderr, 'removed %s from swift' % uuid
    sys.exit(1)

queue = 'retrace_%s' % arch
connection = amqp.Connection(host=config.amqp_host)
channel = connection.channel()
atexit.register(connection.close)
atexit.register(channel.close)
channel.queue_declare(queue=queue, durable=True, auto_delete=False)
# msg:provider
body = amqp.Message('%s:swift' % path)
# Persistent
body.properties['delivery_mode'] = 2
channel.basic_publish(body, exchange='', routing_key=queue)
print 'published %s' % path
