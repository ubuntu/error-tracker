#!/usr/bin/python
import pycassa
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool('crashdb', ['localhost'], timeout=10,
                              credentials=creds)
oops = pycassa.ColumnFamily(pool, 'UserOOPS')

count = 0
for x in oops.get_range(column_count=1):
    count += 1
print count
