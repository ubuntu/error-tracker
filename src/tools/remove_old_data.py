#!/usr/bin/python3

from binascii import hexlify
import sys

from cassandra import OperationTimedOut
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.auth import PlainTextAuthProvider

from datetime import datetime, timedelta
from time import sleep

from daisy import config

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password
)
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)

# use a prepared statement which is less resource intensive
oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key = ?')
oops_delete_stmt = session.prepare('DELETE FROM "OOPS" WHERE key = ?')
dayoops_delete_stmt = session.prepare(
    'DELETE FROM "DayOOPS" WHERE key = ? AND column1 = ?'
)

URL = "https://errors.ubuntu.com/oops/"


def remove_dayoops(date, column1):
    global dry_run
    max_retries = 5
    for i in range(max_retries):
        period = 30 + (30 * i)
        try:
            if not dry_run:
                session.execute(dayoops_delete_stmt, [date, column1])
            break
        except (OperationTimedOut, NoHostAvailable):
            print("Sleeping %ss as we timed out when querying." % period)
            sleep(period)
            continue
        else:
            break
    else:
        print("Cassandra operation timed out %s times." % max_retries)
        return False
    # print("%s %s was removed from DayOOPS" % (date, column1))
    return True


def remove_oops(oops_id):
    global dry_run
    max_retries = 5
    for i in range(max_retries):
        period = 30 + (30 * i)
        try:
            if not dry_run:
                session.execute(oops_delete_stmt, [oops_id])
            break
        except (OperationTimedOut, NoHostAvailable):
            print("Sleeping %ss as we timed out when deleting." % period)
            sleep(period)
            continue
        else:
            break
    else:
        print("Cassandra operation timed out %s times." % max_retries)
        return False
    # print("%s%s was removed from OOPS" % (URL, oops_id.decode()))
    return True


# Main
if __name__ == "__main__":
    global dry_run
    if "--no-dry-run" in sys.argv:
        dry_run = False
        sys.argv.remove("--no-dry-run")
    else:
        dry_run = True
        print(
            "Running by default in dry-run mode. Pass --no-dry-run to really delete stuff."
        )

    # Range of dates for which all OOPSes
    start_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    end_date = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    assert start_date < end_date

    print("Selected time range for deletion: %s - %s" % (start_date, end_date))

    count_success = 0
    count_failure = 0
    try:
        while start_date <= end_date:
            start_date += timedelta(days=1)
            hex_date = "0x" + hexlify(start_date.strftime("%Y%m%d").encode()).decode()

            r_oopses_id = session.execute(
                'SELECT column1, value FROM "DayOOPS" WHERE key = %s' % (hex_date)
            )
            for oops_id in r_oopses_id:
                print(
                    "%s%s is from %s and will be removed... "
                    % (URL, oops_id.value.decode(), start_date),
                    end="",
                )
                if remove_oops(oops_id.value) and remove_dayoops(
                    start_date, oops_id.column1
                ):
                    print(" SUCCESS")
                    count_success += 1
                else:
                    print(" FAILURE")
                    count_failure += 1
    except KeyboardInterrupt:
        pass
    print(
        "Finishing cleaning OOPSes: %s successes and %s failures"
        % (count_success, count_failure)
    )
