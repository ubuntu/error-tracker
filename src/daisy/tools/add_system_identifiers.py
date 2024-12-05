#!/usr/bin/python

import pycassa
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=15,
                              credentials=creds)

useroops_cf = pycassa.ColumnFamily(pool, 'UserOOPS')
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')

if __name__ == '__main__':
    for key, d in useroops_cf.get_range():
        for oops in d.keys():
            oops_cf.insert(oops, {'SystemIdentifier' : key })
