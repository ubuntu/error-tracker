#!/usr/bin/python3

# Remove a specific crash report from the OOPS and UserOOPS tables in the Error Tracker

import sys
from time import sleep

from cassandra import OperationTimedOut
from cassandra.cluster import NoHostAvailable

from errortracker import cassandra

session = cassandra.cassandra_session()

URL = "https://errors.ubuntu.com/oops/"

# Main
if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        dry_run = True
        sys.argv.remove("--dry-run")
    else:
        dry_run = False

    oopsid = sys.argv[1]
    data = {}

    oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key=?')
    oops_delete_stmt = session.prepare('DELETE FROM "OOPS" WHERE key=?')
    useroops_delete_stmt = session.prepare('DELETE FROM "UserOOPS" WHERE key=? AND column1=?')

    max_retries = 5
    for i in range(max_retries):
        period = 30 + (30 * i)
        try:
            oops_data = session.execute(oops_lookup_stmt, [oopsid.encode()])
        except (OperationTimedOut, NoHostAvailable):
            print(f"Sleeping {period}s as we timed out when querying.")
            sleep(period)
            continue
        else:
            break
    else:
        print(f"Cassandra operation timed out {max_retries} times.")
        sys.exit(1)
    # all the column "names" are column1 so make a dictionary of keys: values
    for od in oops_data:
        data[od.column1] = od.value
    systemid = data["SystemIdentifier"]

    if not dry_run:
        for i in range(max_retries):
            period = 30 + (30 * i)
            try:
                session.execute(oops_delete_stmt, [oopsid.encode()])
                session.execute(useroops_delete_stmt, [systemid.encode(), oopsid])
                print(f"{URL}{oopsid} was from {systemid} and had its data removed")
            except (OperationTimedOut, NoHostAvailable):
                print(f"Sleeping {period}s as we timed out when deleting.")
                sleep(period)
                continue
            else:
                break
    else:
        print(f"{URL}{oopsid} was from {systemid} and would have had its data removed")
