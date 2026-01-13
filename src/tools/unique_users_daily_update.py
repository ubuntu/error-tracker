#!/usr/bin/python3

import datetime
import sys

import distro_info
from cassandra.query import SimpleStatement

from errortracker import cassandra

cassandra.setup_cassandra()
session = cassandra.cassandra_session()

d = distro_info.UbuntuDistroInfo()


# Utilities
def _date_range_iterator(start, finish):
    # Iterate all the values including and between the start and finish date
    # string.
    while start <= finish:
        yield start.strftime("%Y%m%d")
        start += datetime.timedelta(days=1)


# Main
if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        dry_run = True
        sys.argv.remove("--dry-run")
    else:
        dry_run = False

    releases = [
        "Ubuntu " + r.replace(" LTS", "")
        for r in sorted(set(d.supported(result="release") + d.supported_esm(result="release")))
    ]
    try:
        releases.append("Ubuntu " + d.devel(result="release"))
    except distro_info.DistroDataOutdated:
        print("Distro info outdated, unable to process devel")

    d = datetime.datetime.today() - datetime.timedelta(days=1)
    formatted = d.strftime("%Y%m%d")
    for release in releases:
        print(f"Updating {release}")
        i = _date_range_iterator(d - datetime.timedelta(days=89), d)
        users = set()
        day_count = 0
        for date in i:
            print(f"  processing {date} - ", end="")
            day_count += 1
            user_count = 0
            hex_daterelease = ("%s:%s" % (release, date)).encode()
            # column1 is the system uuid
            results = session.execute(
                SimpleStatement(f'SELECT column1 FROM {session.keyspace}."DayUsers" WHERE key=%s'),
                [hex_daterelease],
            )
            rows = [row for row in results]
            user_count += len(rows)
            users.update([row["column1"] for row in rows])
            print(f"found {user_count} users")
        # value is the number of users
        uu_results = session.execute(
            SimpleStatement(
                f'SELECT value from {session.keyspace}."UniqueUsers90Days" WHERE key=%s and column1=%s'
            ),
            [release, formatted],
        )
        try:
            uu_count = [r["value"] for r in uu_results][0]
        except IndexError:
            uu_count = 0
        print(("Was %s" % uu_count))
        print(("Now %s" % len(users)))
        if not dry_run:
            session.execute(
                SimpleStatement(
                    "INSERT INTO %s.\"%s\" (key, column1, value) \
                             VALUES ('%s', '%s', %d)"
                    % (session.keyspace, "UniqueUsers90Days", release, formatted, len(users))
                )
            )
        print(("%s:%s" % (release, len(users))))
        print(("from %s days" % day_count))
