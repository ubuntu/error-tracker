#!/usr/bin/python3

import sys

from errors import cassie
from errortracker import amqp_utils, cassandra

cassandra.setup_cassandra()

ARCHES = ["amd64", "arm64", "armhf", "i386"]


def main():
    if "--dry-run" in sys.argv:
        dry_run = True
        sys.argv.remove("--dry-run")
    else:
        dry_run = False

    for arch in ARCHES:
        queue = f"retrace_{arch}"
        length = amqp_utils.get_queue_length(queue)
        if length is None:
            print(f"{queue}: connection error")
            continue
        print(f"{queue}: {length}")
        if not dry_run:
            cassie.record_queue_length(queue, length)

    for arch in ARCHES:
        queue = f"failed_retrace_{arch}"
        length = amqp_utils.get_queue_length(queue)
        if length is None:
            print(f"{queue}: connection error")
            continue
        print(f"{queue}: {length}")
        if not dry_run:
            cassie.record_queue_length(queue, length)


if __name__ == "__main__":
    main()
