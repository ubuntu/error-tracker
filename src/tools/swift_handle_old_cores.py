#!/usr/bin/python3

# iterate over the core files in swift and if they are rather old assume they
# got dropped from the amqp queue somehow and readd them after looking up the
# arch and release for the core file in cassandra.

import atexit
import sys
from datetime import datetime, timedelta, timezone

import amqp
import swiftclient

from errortracker import amqp_utils, cassandra, config, swift_utils, utils

limit = None
if len(sys.argv) == 2:
    limit = int(sys.argv[1])

swift_client = swift_utils.get_swift_client()
bucket = config.swift_bucket

session = cassandra.cassandra_session()

connection = amqp_utils.get_connection()
channel = connection.channel()
atexit.register(connection.close)
atexit.register(channel.close)

now = datetime.now(timezone.utc)
abitago = now - timedelta(7)
count = 0
queued_count = 0
removed_count = 0


def remove_core(bucket, core):
    global removed_count
    try:
        swift_client.delete_object(bucket, core)
        removed_count += 1
        print("removed %s from swift" % core, file=sys.stderr)
    except swiftclient.client.ClientException as e:
        if "404 Not Found" in str(e):
            # It may have already been removed
            print("%s not found in swift" % core, file=sys.stderr)


for container in swift_client.get_container(container=bucket, limit=limit):
    # the dict is the metadata for the container
    if isinstance(container, dict):
        continue
    oops_lookup = session.prepare('SELECT value FROM "OOPS" WHERE key=? and column1=?')
    for core in container:
        uuid = core["name"]
        count += 1
        try:
            arch = session.execute(oops_lookup, [uuid.encode(), "Architecture"]).one()[0]
        except (IndexError, TypeError):
            arch = ""
        if not arch:
            print("could not find architecture for %s" % uuid, file=sys.stderr)
            remove_core(bucket, uuid)
            continue
        try:
            release = session.execute(oops_lookup, [uuid.encode(), "DistroRelease"]).one()[0]
        except (IndexError, TypeError):
            release = ""
        if not release:
            print("could not find release for %s" % uuid, file=sys.stderr)
            remove_core(bucket, uuid)
            continue
        if not utils.retraceable_release(release):
            print(
                "Unretraceable or EoL release (%s) in %s" % (uuid, release),
                file=sys.stderr,
            )
            remove_core(bucket, uuid)
            continue
        try:
            fail_reason = session.execute(
                oops_lookup, [uuid.encode(), "RetraceFailureReason"]
            ).one()[0]
        except (IndexError, TypeError):
            fail_reason = ""
        # these were already retraced these but the core wasn't removed for
        # some reason
        if fail_reason:
            print("RetraceFailureReason found for %s" % uuid, file=sys.stderr)
            remove_core(bucket, uuid)
            continue
        core_date = datetime.strptime(core["last_modified"], "%Y-%m-%dT%H:%M:%S.%f%z")
        # it may still be in the queue awaiting its first retrace attempt
        if core_date > abitago:
            print("skipping too new core %s" % uuid)
            continue
        # don't use resources retrying these arches
        if arch in ["", "ppc64el", "arm64", "armhf"]:
            print("architecture less important for %s" % uuid, file=sys.stderr)
            remove_core(bucket, uuid)
            continue

        queue = "retrace_%s" % arch
        channel.queue_declare(queue=queue, durable=True, auto_delete=False)
        # msg:provider
        body = amqp.Message("%s:swift" % uuid)
        # Persistent
        body.properties["delivery_mode"] = 2
        channel.basic_publish(body, exchange="", routing_key=queue)
        print("published %s to %s queue" % (uuid, arch))
        queued_count += 1

    print(
        "Finished, reviewed %i cores (%i removed, %i requeued)."
        % (count, removed_count, queued_count)
    )
