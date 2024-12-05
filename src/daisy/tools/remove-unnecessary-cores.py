#!/usr/bin/python

# Using a text file with OOPS ids, remove them from the retracing queue and
# swift storage.

# 2014-11-07
# remove core files with an OOPS without a SAS
# remove core files with an OOPS with a package version of (not installed)

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
    if not addr_sig:
        return
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

with open('swift-cores.txt', 'r') as cores:
    cs = getattr(config, 'core_storage', '')
    if not cs:
        print('core_storage not set.')
        sys.exit(1)
    provider_data = cs['swift']
    for line in cores:
        oopsid = line.strip()
        try:
            oops_data = oops_cf.get(oopsid,
                                    columns=['Date','StacktraceAddressSignature',
                                             'Package'])
        except pycassa.NotFoundException:
            # this could happen for things already retraced
            print("OOPS %s not found in OOPS CF." % oopsid)
            continue

        package = oops_data.get('Package', '')
        version = ' '.join(package.split(' ')[1:])
        sas = oops_data.get('StacktraceAddressSignature', '')
        count += 1
        if count > 100:
            sys.exit(0)
        # packages with a version equal to "(not installed)" are generally
        # from 3rd party debs e.g. skype and chromium-browser
        if '(not installed)' not in version and sas:
            continue
        #if '(not installed)' in version:
        #    print("Would remove not installed https://errors.ubuntu.com/oops/%s" % oopsid)
        #if not sas:
        #    print("Would remove no SAS https://errors.ubuntu.com/oops/%s" % oopsid)
        remove_from_retracing(oopsid)
        remove_from_swift(oopsid, provider_data)
