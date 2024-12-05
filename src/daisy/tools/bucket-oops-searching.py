#!/usr/bin/python3

# Using the 'bucket_id' from the page source of an errors bucket search for
# details about individual crashes which are part of a bucket

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

from binascii import hexlify

from daisy import config, utils

import sys
import urllib

URL = "https://errors.ubuntu.com/oops/"

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username,
    password=config.cassandra_password)

cluster = Cluster(['192.168.10.2'], auth_provider=auth_provider)
                  # version 1 is needed for canonistack
                  #protocol_version=1)
session = cluster.connect(config.cassandra_keyspace)

input = sys.argv[1]
bucket_id = urllib.parse.unquote(input)

# https://stackoverflow.com/questions/18955750/cassandra-2-cqlengine-store-images-error
# the keys in the ColumnFamilies are all blobs
# double quotes are needed to protect the case-sensitive table names
bucket_data = session.execute("SELECT column1 FROM \"Bucket\" WHERE key = '%s'"
                              % bucket_id)
# use a prepared statement which is less resource intensive
oops_lookup_stmt = session.prepare("SELECT * FROM "OOPS" WHERE key=?")

for bucket in bucket_data:
    data = {}
    oops = bucket.column1
    # 2022-06-29 Is this causing an issue?
    oops_data = session.execute(oops_lookup_stmt, [str(oops).encode()])
    # all the column "names" are column1 so make a dictionary of keys: values
    for od in oops_data:
        data[od.column1] = od.value
        continue
    # Might be useful for a different query
    #if 'Package' in data:
    #    package, version = utils.split_package_and_version(data['Package'])
    deps = {}
    if 'Dependencies' in data:
        for line in data['Dependencies'].split('\n'):
            pkg, version = utils.split_package_and_version(line)
            deps[pkg] = version
    # TODO make these cli parameters
    search_package = 'libfreerdp2-2'
    search_version = '2.6.1+dfsg1-3ubuntu2.2'
    # TODO it might also be nice to filter on Date given that we know nobody
    # could have installed the package before it was accepted to -proposed /
    # -updates.
    if search_package.encode() in deps:
        print("%s%s crashed on %s has %s %s" %
              (URL, oops, data['Date'], search_package,
               deps[search_package.encode()].decode()))
    # TODO printing a summary of information like the following would have
    # been better
    # $ cat libfreerdp2-pkg-versions.txt | awk {'print $11'} | sort | uniq -c
    # 121 2.6.1+dfsg1-3ubuntu1
    #  41 2.6.1+dfsg1-3ubuntu2
    #  73 2.6.1+dfsg1-3ubuntu2.1


cluster.shutdown()
