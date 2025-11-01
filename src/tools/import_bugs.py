#!/usr/bin/python3

import sqlite3
from urllib.request import urlretrieve

from errortracker import cassandra

session = cassandra.cassandra_session()

bm_table_insert = session.prepare(
    "INSERT INTO \"BucketMetadata\" (key, column1, value) VALUES (?, 'LaunchpadBug', ?)"
)
b2c_table_insert = session.prepare(
    'INSERT INTO "BugToCrashSignatures" (key, column1, value) VALUES (?, ?, 0x)'
)

DB_URL = "https://ubuntu-archive-team.ubuntu.com/apport-duplicates/apport_duplicates.db"
SCRATCH_DB = "/tmp/apport_duplicates.db"


def import_bug_numbers(path):
    connection = sqlite3.connect(path)
    # The apport duplicates database mysteriously has lots of dpkg logs in it.
    sql = "SELECT crash_id, signature FROM crashes WHERE signature NOT LIKE ?"
    for crash_id, signature in connection.execute(sql, ("%%\n%%",)):
        print(f"Inserting LP: #{crash_id} as '{signature}'")
        session.execute(bm_table_insert, [signature.encode("utf-8"), str(crash_id)])
        session.execute(b2c_table_insert, [crash_id, signature])


if __name__ == "__main__":
    print(f"Downloading database in {SCRATCH_DB}")
    urlretrieve(DB_URL, SCRATCH_DB)
    import_bug_numbers(SCRATCH_DB)
