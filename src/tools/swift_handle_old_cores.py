#!/usr/bin/python3

# iterate over the core files in swift and if they are rather old assume they
# got dropped from the amqp queue somehow and readd them after looking up the
# arch and release for the core file in cassandra.

import atexit
import sys
from datetime import datetime, timedelta, timezone

import amqp
import swiftclient
from cassandra.cqlengine.query import DoesNotExist

from errortracker import amqp_utils, cassandra, cassandra_schema, config, swift_utils, utils

swift_client = swift_utils.get_swift_client()

cassandra.setup_cassandra()

connection = amqp_utils.get_connection()
channel = connection.channel()
atexit.register(connection.close)
atexit.register(channel.close)

NOW = datetime.now(timezone.utc)
ONE_WEEK_AGO = NOW - timedelta(days=7)
ONE_MONTH_AGO = NOW - timedelta(days=30)

REMOVE = 0
SKIP = 1
QUEUE = 2


def remove_core(uuid):
    try:
        swift_client.delete_object(config.swift_bucket, uuid)
        print("removed %s from swift" % uuid, file=sys.stderr)
    except swiftclient.client.ClientException as e:
        if "404 Not Found" in str(e):
            # It may have already been removed
            print("%s not found in swift" % uuid, file=sys.stderr)


def handle_core(uuid, core_date):
    global channel, connection
    try:
        arch = cassandra_schema.OOPS.get(key=uuid.encode(), column1="Architecture").value
    except DoesNotExist:
        print("could not find architecture for %s" % uuid, file=sys.stderr)
        return REMOVE
    try:
        release = cassandra_schema.OOPS.get(key=uuid.encode(), column1="DistroRelease").value
        if not utils.retraceable_release(release):
            print(
                "Unretraceable or EoL release (%s) in %s" % (uuid, release),
                file=sys.stderr,
            )
            return REMOVE
    except DoesNotExist:
        print("could not find release for %s" % uuid, file=sys.stderr)
        return REMOVE
    try:
        fail_reason = cassandra_schema.OOPS.get(
            key=uuid.encode(), column1="RetraceFailureReason"
        ).value
        # these were already retraced these but the core wasn't removed for
        # some reason
        if fail_reason:
            print("RetraceFailureReason found for %s" % uuid, file=sys.stderr)
            return REMOVE
    except DoesNotExist:
        pass
    # a backlog of more than one month doesn't make sense
    if core_date < ONE_MONTH_AGO:
        print("dropping too old core (%s) %s" % (core_date, uuid))
        return REMOVE
    # it may still be in the queue awaiting its first retrace attempt
    if core_date > ONE_WEEK_AGO:
        print("skipping too new core (%s) %s" % (core_date, uuid))
        return SKIP
    # don't use resources retrying these arches
    if arch not in ["amd64", "arm64"]:
        print("less important architecture for %s" % uuid, file=sys.stderr)
        return REMOVE

    queue = "retrace_%s" % arch
    # msg:provider
    body = amqp.Message("%s:swift" % uuid)
    # Persistent
    body.properties["delivery_mode"] = 2
    try:
        channel.basic_publish(body, exchange="", routing_key=queue)
    except OSError:
        # don't bother with retry loops here, next run will handle it
        print("skipped, failed to publish (broken pipe) %s" % uuid)
        connection = amqp_utils.get_connection()
        channel = connection.channel()
        return SKIP
    print("published %s to %s queue (received %s)" % (uuid, arch, core_date))
    return QUEUE


def main():
    count = 0
    queued_count = 0
    removed_count = 0
    skipped_count = 0
    for arch in ["amd64", "arm64"]:
        channel.queue_declare(queue=f"retrace_{arch}", durable=True, auto_delete=False)
    for container in swift_client.get_container(container=config.swift_bucket, full_listing=True):
        # the dict is the metadata for the container
        if isinstance(container, dict):
            continue
        try:
            for core in container:
                count += 1
                uuid = core["name"]
                core_date = datetime.strptime(core["last_modified"], "%Y-%m-%dT%H:%M:%S.%f%z")
                ret = handle_core(uuid, core_date)
                if ret == QUEUE:
                    queued_count += 1
                elif ret == SKIP:
                    skipped_count += 1
                elif ret == REMOVE:
                    remove_core(uuid)
                    removed_count += 1
        except KeyboardInterrupt:
            print("Stopping on user input")

        print(
            f"Finished, reviewed {count} cores ({removed_count} removed, {queued_count} requeued, {skipped_count} skipped)."
        )


if __name__ == "__main__":
    main()
