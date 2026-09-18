#!/usr/bin/python3

# Remove all the OOPSes filed on a range of dates, to free up space in the
# database. Note that this doesn't clean the Buckets pointing to those OOPSes,
# see clean_buckets.py for that.

import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta
from pathlib import Path

from cassandra import OperationTimedOut, Timeout, Unauthorized
from cassandra.cluster import NoHostAvailable
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

sys.path.insert(0, str(Path(__file__).parent.parent))

from errortracker import cassandra  # noqa: E402
from errortracker.cassandra_schema import OOPS, DayOOPS  # noqa: E402

cassandra.setup_cassandra()

URL = "https://errors.ubuntu.com/oops/"


def parse_args():
    parser = ArgumentParser(description="Remove old OOPS data from the Error Tracker")
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually delete the data, instead of only reporting what would be removed",
    )
    parser.add_argument("start_date", help="The first date to remove, as YYYY-MM-DD")
    parser.add_argument("end_date", help="The last date to remove, as YYYY-MM-DD")
    return parser.parse_args()


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(),
    retry=retry_if_exception_type((Timeout, NoHostAvailable, OperationTimedOut, Unauthorized)),
)
def remove_oops(oops_id):
    OOPS.objects.filter(key=oops_id).delete()


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(),
    retry=retry_if_exception_type((Timeout, NoHostAvailable, OperationTimedOut, Unauthorized)),
)
def remove_dayoops(day_key):
    DayOOPS.objects.filter(key=day_key.encode()).delete()


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(),
    retry=retry_if_exception_type((Timeout, NoHostAvailable, OperationTimedOut, Unauthorized)),
)
def remove_day(day, dry_run):
    """Remove every OOPS filed on the given datetime.date, returning how many
    were found."""
    day_key = day.strftime("%Y%m%d")
    count = 0
    for oops in DayOOPS.objects.filter(key=day_key.encode()).limit(None):
        oops_id = oops.value
        print(f"{URL}{oops_id.decode()} is from {day} and will be removed... ", end="")
        count += 1
        if dry_run:
            print("SKIPPED (dry-run)")
            continue
        remove_oops(oops_id)
        print("SUCCESS")
    if not dry_run:
        remove_dayoops(day_key)
    return count


def main():
    args = parse_args()
    dry_run = not args.no_dry_run
    if dry_run:
        print("Running by default in dry-run mode. Pass --no-dry-run to really delete stuff.")

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    assert start_date < end_date

    print(f"Selected time range for deletion: {start_date} - {end_date}")

    count = 0
    try:
        while start_date <= end_date:
            count += remove_day(start_date, dry_run)
            start_date += timedelta(days=1)
    except KeyboardInterrupt:
        pass
    verb = "would be removed" if dry_run else "were removed"
    print(f"Finishing cleaning OOPSes: {count} {verb}")


if __name__ == "__main__":
    main()
