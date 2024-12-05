#!/usr/bin/python
import pycassa
import sys
from pycassa.cassandra.ttypes import NotFoundException
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool('crashdb', ['localhost'], timeout=10,
                              credentials=creds)
oops = pycassa.ColumnFamily(pool, 'OOPS')
indexes = pycassa.ColumnFamily(pool, 'Indexes')

present = 0
gone = 0
with open(sys.argv[1], 'r') as fp:
    for line in fp:
        o = line.rsplit('/', 1)[1].strip('\n')
        try:
            sas = oops.get(o, columns=['StacktraceAddressSignature'])['StacktraceAddressSignature']
        except NotFoundException:
            # There were some in progress .crash and .core files in the mix
            print 'no SAS for', o
            continue
        try:
            indexes.get('retracing', columns=[sas])
            present += 1
        except NotFoundException:
            gone += 1

print present, 'still present'
print gone, 'removed'
