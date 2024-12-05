#!/usr/bin/python

# Using a text file with OOPS ids, remove them from the retracing queue and
# swift storage

import pycassa
import sys
from daisy import config

_cached_swift = None
creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=10,
                              credentials=creds)
consistency_level = pycassa.ConsistencyLevel.LOCAL_QUORUM
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
indexes_cf = pycassa.ColumnFamily(pool, 'Indexes')

count = 0

def remove_from_retracing(oops_id):
    addr_sig = oops_cf.get(oops_id,
                    ['StacktraceAddressSignature', 'SystemIdentifier'])
    addr_sig = addr_sig.values()[0]
    try:
        #if indexes_cf.get('retracing', [addr_sig]):
        #    print("Found OOPS %s in retracing queue" % oops_id)
        indexes_cf.remove('retracing', [addr_sig])
        print("OOPS %s removed from retracing queue" % oops_id)
    except pycassa.NotFoundException:
        print("OOPS %s not found in retracing queue" % oops_id)

def remove_from_swift(key, provider_data):
    global _cached_swift
    import swiftclient
    opts = {'tenant_name': provider_data['os_tenant_name'],
            'region_name': provider_data['os_region_name']}
    try:
        if not _cached_swift:
            _cached_swift = swiftclient.client.Connection(
                        provider_data['os_auth_url'],
                        provider_data['os_username'],
                        provider_data['os_password'], os_options=opts,
                        auth_version='2.0')
        #print('swift token: %s' % str( _cached_swift.token))
        bucket = provider_data['bucket']
        _cached_swift.delete_object(bucket, key)
        print('Removed %s (swift):' % key)
    except swiftclient.client.ClientException:
        print('Could not remove %s (swift):' % key)

with open('unqueued-cores.txt', 'r') as unqueued:
    cs = getattr(config, 'core_storage', '')
    if not cs:
        print('core_storage not set.')
        sys.exit(1)
    provider_data = cs['swift']
    for line in unqueued:
        oopsid = line.strip('\n')
        try:
            oops_data = oops_cf.get(oopsid, columns=['Date'])
        except pycassa.NotFoundException:
            print("OOPS %s not found in OOPS CF." % oopsid)
        remove_from_retracing(oopsid)
        remove_from_swift(oopsid, provider_data)
        #count += 1
        #if count > 10:
        #    break
