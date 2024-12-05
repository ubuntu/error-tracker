#!/usr/bin/python

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement

import sqlite3
import sys

from binascii import hexlify
from daisy import config


auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password)
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)
session.default_consistency_level = ConsistencyLevel.LOCAL_ONE


def import_bug_numbers(path):
    connection = sqlite3.connect(path)
    # The apport duplicates database mysteriously has lots of dpkg logs in it.
    sql = 'select crash_id, signature from crashes where signature not like ?'
    lpb = 'LaunchpadBug'
    bm_table = 'BucketMetadata'
    b2c_table = 'BugToCrashSignatures'
    for crash_id, signature in connection.execute(sql, ('%%\n%%',)):
        hex_sig = '0x' + hexlify(signature.encode('utf-8'))
        hex_empty = '0x' + hexlify('')
        # need to quote single quotes for cql
        cql_sig = signature.encode('utf-8').replace("'", "''")
        session.execute(SimpleStatement
            ("INSERT INTO \"%s\" (key, column1, value) VALUES (%s, '%s', '%s')"
             % (bm_table, hex_sig, lpb, crash_id)))
        session.execute(SimpleStatement
            ("INSERT INTO \"%s\" (key, column1, value) VALUES (%s, '%s', %s)"
             % (b2c_table, crash_id, cql_sig, hex_empty)))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print >>sys.stderr, 'Usage: %s <apport_duplicates.db>' % sys.argv[0]
        sys.exit(1)
    import_bug_numbers(sys.argv[1])
