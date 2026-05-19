#!/usr/bin/python2.7

# Delete all the crash reports from a specific systemid like
# https://errors.ubuntu.com/user/cfc8a68e9841db904b074a1135c3e6514ac806e675445489d5ad3aa09633fe2d968c6918cb9f343f2c7a353461ab93afcbccf176af756b7426f75935afc64cb2

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

    o_data = {}
    target_systemid = sys.argv[1]

    system_lookup_stmt = session.prepare(
        'SELECT * FROM "UserOOPS" WHERE key=?')
    oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key=?')
    oops_delete_stmt = session.prepare('DELETE FROM "OOPS" WHERE key = ?')

    max_retries = 5
    for i in range(max_retries):
        period = 30 + (30 * i)
        try:
            system_data = session.execute(system_lookup_stmt,
                                          [target_systemid])
        except (OperationTimedOut, NoHostAvailable):
            print("Sleeping %ss as we timed out when querying." % period)
            sleep(period)
            continue
        else:
            break
    else:
        print("Cassandra operation timed out %s times." % max_retries)
        sys.exit(1)
    # column1 is the oopsid
    crashes = [row.column1 for row in system_data]
    for oopsid in crashes:
        max_retries = 5
        for i in range(max_retries):
            period = 30 + (30 * i)
            try:
                oops_data = session.execute(oops_lookup_stmt, [oopsid])
                break
            except (OperationTimedOut, NoHostAvailable):
                print("Sleeping %ss as we timed out when querying." % period)
                sleep(period)
                continue
            else:
                break
        else:
            print("Cassandra operation timed out %s times." % max_retries)
            sys.exit(1)
        # all the column "names" are column1 so make a dictionary of keys:
        # values
        for od in oops_data:
            o_data[od.column1] = od.value
        try:
            systemid = o_data['SystemIdentifier']
        except KeyError:
            systemid = ''
        if systemid != target_systemid:
            continue
            print("systemid for %s doesn't equal the target systemid" %
                  oopsid)
        max_retries = 5
        for i in range(max_retries):
            period = 30 + (30 * i)
            if not dry_run:
                try:
                    session.execute(oops_delete_stmt, [oopsid])
                    print("%s%s was from %s and had its data removed" %
                          (URL, oopsid, systemid))
                    break
                except (OperationTimedOut, NoHostAvailable):
                    print("Sleeping %ss as we timed out when deleting." %
                          period)
                    sleep(period)
                    continue
                else:
                    break
