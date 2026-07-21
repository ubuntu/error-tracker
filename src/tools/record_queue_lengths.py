#!/usr/bin/python3

import argparse
import datetime

from errors import cassie
from errortracker import amqp_utils, cassandra, cassandra_schema

ARCHES = ["amd64", "arm64", "armhf", "i386"]


def prune_queue_lengths(days: int) -> int | None:
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y%m%d%H%M")
    try:
        rows = cassandra_schema.Indexes.objects.filter(key=b"retrace_queue_length").all()
    except cassandra_schema.DoesNotExist:
        return

    pruned = 0
    for row in rows:
        timestamp = row.column1.split(":", 1)[1]
        if timestamp < cutoff_str:
            print(f"  Removing {row.column1} ({row.value.decode()})")
            row.delete()
            pruned += 1
    print(f"Pruned {pruned} entries older than {days} days.")


def parse_args():
    parser = argparse.ArgumentParser(description="Record retrace queue lengths.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print queue lengths without recording them",
    )
    parser.add_argument(
        "--prune-days",
        type=int,
        metavar="DAYS",
        help="Remove queue length entries older than DAYS",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    cassandra.setup_cassandra()

    if args.prune_days:
        prune_queue_lengths(args.prune_days)

    for queue_prefix in ["retrace", "failed_retrace"]:
        for arch in ARCHES:
            queue = f"{queue_prefix}_{arch}"
            length = amqp_utils.get_queue_length(queue)
            if length is None:
                print(f"{queue}: None (connection error?)")
                continue
            print(f"{queue}: {length}")
            if not args.dry_run:
                cassie.record_queue_length(queue, length)


if __name__ == "__main__":
    main()
