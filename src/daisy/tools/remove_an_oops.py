#!/usr/bin/python2.7

# Remove a specific crash report from the OOPS table in the Error Tracker

import os
import sys

from cassandra import ConsistencyLevel, OperationTimedOut
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement

from time import sleep

from daisy import config

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password)
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)
session.default_consistency_level = ConsistencyLevel.LOCAL_ONE

URL = "https://errors.ubuntu.com/oops/"

# Main
if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        dry_run = True
        sys.argv.remove('--dry-run')
    else:
        dry_run = False

    oopsid = sys.argv[1]
    data = {}

    oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key=?')
    oops_delete_stmt = session.prepare('DELETE FROM "OOPS" WHERE key = ?')

    max_retries = 5
    for i in range(max_retries):
        period = 30 + (30 * i)
        try:
            oops_data = session.execute(oops_lookup_stmt, [oopsid])
        except (OperationTimedOut, NoHostAvailable):
            print("Sleeping %ss as we timed out when querying." % period)
            sleep(period)
            continue
        else:
            break
    else:
        print("Cassandra operation timed out %s times." % max_retries)
        sys.exit(1)
    # all the column "names" are column1 so make a dictionary of keys: values
    for od in oops_data:
        data[od.column1] = od.value
    systemid = data['SystemIdentifier']

    if not dry_run:
        for i in range(max_retries):
            period = 30 + (30 * i)
            try:
                session.execute(oops_delete_stmt, [oopsid, '%s' % column])
                print("%s%s was from %s and had its data removed" %
                      (URL, oopsid, systemid))
            except (OperationTimedOut, NoHostAvailable):
                print("Sleeping %ss as we timed out when deleting." % period)
                sleep(period)
                continue
            else:
                break
    else:
        print("%s%s was from %s and would have had its data removed" %
              (URL, oopsid, systemid))
