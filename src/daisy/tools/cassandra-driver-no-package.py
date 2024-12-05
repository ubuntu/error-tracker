#!/usr/bin/python3

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

from binascii import hexlify

from daisy import config, utils

import sys

URL = "https://errors.ubuntu.com/oops/"

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username,
    password=config.cassandra_password)

cluster = Cluster(['192.168.10.2'], auth_provider=auth_provider)
                  # version 1 is needed for canonistack
                  #protocol_version=1)
session = cluster.connect(config.cassandra_keyspace)

date = sys.argv[1].encode()

# https://stackoverflow.com/questions/18955750/cassandra-2-cqlengine-store-images-error
# the keys in the ColumnFamilies are all blobs
hex_date = '0x' + hexlify(date).decode()
oopses = session.execute('SELECT * FROM "DayOOPS" WHERE key = %s LIMIT 2000' % hex_date)

# use a prepared statement which is less resource intensive
oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key=?')

missing_data = {}
for oops in oopses:
    data = {}
    #hex_oops = '0x' + hexlify(oops.value)
    # double quotes are needed to make table names case-sensitive
    #oops_data = session.execute('SELECT * FROM "OOPS" WHERE key = %s' %
    #    hex_oops)
    oops_data = session.execute(oops_lookup_stmt, [oops.value])
    # all the column "names" are column1 so make a dictionary of keys: values
    for od in oops_data:
        data[od.column1] = od.value
    if 'Package' not in data:
        continue
    package, version = utils.split_package_and_version(data['Package'])
    # print("%s" % package)
    if not package:
        print("%s%s missing package name" % (URL, oops.value))
    if not version:
        if package not in missing_data:
            missing_data[package] = [oops.value]
        else:
            missing_data[package].append(oops.value)

for datum in missing_data:
    print("Errors regarding %s missing package version" % (datum))
    for oops in missing_data[datum]:
        print("    %s%s" % (URL, oops))
