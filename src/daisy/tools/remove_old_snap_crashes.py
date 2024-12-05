#!/usr/bin/python2.7

import os
import sys

from cassandra import ConsistencyLevel, OperationTimedOut
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement

from binascii import hexlify
from time import sleep

from daisy import config

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password)
# use my secret ssh tunnel
#config.cassandra_hosts = ['192.168.10.2']
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)
session.default_consistency_level = ConsistencyLevel.LOCAL_ONE

URL = "https://errors.ubuntu.com/oops/"

def check_and_remove_oops(oopsid):
    data = {}
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
        return
        # sys.exit(1)
    # all the column "names" are column1 so make a dictionary of keys: values
    for od in oops_data:
        data[od.column1] = od.value
    if data.get('ProblemType', '') == 'Snap':
        print("%s%s was about a snap and had its data removed" %
              (URL, dayoops_row.value))
        for i in range(max_retries):
            period = 30 + (30 * i)
            try:
                session.execute(oops_delete_stmt, [oopsid])
            except (OperationTimedOut, NoHostAvailable):
                print("Sleeping %ss as we timed out when deleting." % period)
                sleep(period)
                continue
            else:
                break
        else:
            print("Cassandra operation timed out %s times." % max_retries)
            return


# Main
if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        dry_run = True
        sys.argv.remove('--dry-run')
    else:
        dry_run = False

    date = sys.argv[1]

    hex_date = '0x' + hexlify(date)

    # 2020-08-25 Traceback'ed due to no hosts for query?
    # cassandra.cluster.NoHostAvailable: ('Unable to complete the operation
    # against any hosts', {<Host: 192.168.10.2 juju>: TypeError("object of
    # type 'ResultSet' has no len()",), <Host: 10.22.96.39 juju>:
    # ConnectionException('Host has been marked down or removed',)})
    #query = session.execute("SELECT * FROM \"DayOOPS\" WHERE key = %s" %
    #                        hex_date)
    #statement = SimpleStatement(query, fetch_size=100)

    dayoopses = session.execute('SELECT * FROM "DayOOPS" WHERE key = %s '
                                'LIMIT 2000' % hex_date)
    # use a prepared statement which is less resource intensive
    oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key=?')
    oops_delete_stmt = session.prepare('DELETE FROM "OOPS" WHERE key = ?')

    removal_progress = 'remove_old_snap_crashes-%s.txt' % date
    if os.path.exists(removal_progress):
        with open(removal_progress, 'r') as f:
            last_row = f.readline()
    else:
        last_row = ''

    run = 1
    if last_row == '':
        print('%s run: %s' % (date, run))
        #for dayoops_row in session.execute(statement):
        for dayoops_row in dayoopses:
            check_and_remove_oops(dayoops_row.value)
            last_row = dayoops_row.column1
        run += 1

    while run < 150:
        if not last_row:
            break
        dayoops_row = ''
        # use a prepared statement here
        dayoopses2 = session.execute('SELECT * FROM "DayOOPS" WHERE key = %s '
                                     'AND column1 > %s LIMIT 2000' %
                                     (hex_date, last_row))
        print('%s run: %s' % (date, run))
        for dayoops_row in dayoopses2:
            check_and_remove_oops(dayoops_row.value)
            last_row = dayoops_row.column1
        if dayoops_row:
            with open(removal_progress, 'w') as f:
                f.write(str(dayoops_row.column1))
        run += 1
