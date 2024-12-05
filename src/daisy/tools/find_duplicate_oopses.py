#!/usr/bin/python
import pycassa
from daisy import config
from pycassa.cassandra.ttypes import NotFoundException

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=10,
                              credentials=creds)
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
useroops = pycassa.ColumnFamily(pool, 'UserOOPS')

total_unique_count = 0
total_dupe_count = 0
system_count = 0
for system, oopses in useroops.get_range(column_count=20, row_count=1000):
    print(system)
    system_count += 1
    unique_count = 0
    duplicate_count = 0
    identifiers = []
    for oops in oopses.keys():
        # date isn't unique enough so use ExecutablePath too
        # e.g
        # https://errors.ubuntu.com/oops/adc8b3f0-f235-11e3-929d-fa163e22e467
        # https://errors.ubuntu.com/oops/82d7eb02-f235-11e3-8682-fa163e373683
        try:
            oops_data = oops_cf.get(oops, ['Date', 'ExecutablePath'])
        except NotFoundException:
            continue
        date = oops_data['Date']
        epath = oops_data.get('ExecutablePath', '')
        if not epath:
            continue
        identifier = '%s:%s' % (date, epath)
        if identifier in identifiers:
            duplicate_count += 1
        else:
            identifiers.append(identifier)
            unique_count += 1
        print('  %s %s' % (oops, identifier))
    print('  unique crashes: %i' % unique_count)
    print('  duplicate crashes: %i' % duplicate_count)
    total_unique_count += unique_count
    total_dupe_count += duplicate_count
print('systems reviewed: %i' % system_count)
print('total unique crashes: %i' % total_unique_count)
print('total duplicate crashes: %i' % total_dupe_count)
