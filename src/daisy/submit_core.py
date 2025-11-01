#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright © 2011-2013 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import random
import socket
from datetime import datetime, timezone

import amqp
from cassandra.cqlengine.query import DoesNotExist

# from daisy import config
from daisy.metrics import get_metrics
from errortracker import amqp_utils, cassandra_schema, config, swift_utils

metrics = get_metrics("daisy.%s" % socket.gethostname())
logger = logging.getLogger("daisy")


def write_policy_allow(oops_id, bytes_used, provider_data):
    if provider_data.get("usage_max_mb"):
        usage_max = provider_data["usage_max_mb"] * 1024 * 1024
        # Random Early Drop policy: random drop with p-probality as:
        # 0 if <50%, then linearly (50%,100%) -> (0,1)
        if (50 + random.randint(0, 49)) < (100 * bytes_used / usage_max):
            logger.info(
                "Skipping oops_id={oops_id} save to type={st_type}, "
                "bytes_used={bytes_used}, usage_max={usage_max}".format(
                    oops_id=oops_id,
                    st_type=provider_data["type"],
                    bytes_used=bytes_used,
                    usage_max=usage_max,
                )
            )
            metrics.meter("submit_core.random_early_drop")
            return False
    return True


def swift_delete_ignoring_error(swift_cmd, bucket, oops_id):
    from subprocess import CalledProcessError, check_call

    swift_delete_cmd = swift_cmd + ["delete", bucket, oops_id]
    try:
        check_call(swift_delete_cmd)
    except CalledProcessError:
        pass


def write_to_swift(fileobj: bytes, oops_id: str):
    """Write the core file to OpenStack Swift."""
    try:
        swift_utils.get_swift_client().put_object(config.swift_bucket, oops_id, fileobj)
    except Exception as e:
        logger.error(
            "error when trying to add (%s) to bucket: %s"
            % (
                oops_id,
                str(e),
            )
        )
        return False
    logger.info("CORE for (%s) written to bucket" % (oops_id))
    return True


def write_to_amqp(message, arch):
    queue = "retrace_%s" % arch
    channel = amqp_utils.get_connection().channel()
    if not channel:
        return False
    try:
        channel.queue_declare(queue=queue, durable=True, auto_delete=False)
        # We'll use this timestamp to measure how long it takes to process a
        # retrace, from receiving the core file to writing the data back to
        # Cassandra.
        body = amqp.Message(message, timestamp=int(datetime.now(timezone.utc).timestamp()))
        # Persistent
        body.properties["delivery_mode"] = 2
        channel.basic_publish(body, exchange="", routing_key=queue)
        msg = "%s added to %s queue" % (message.split(":")[0], queue)
        logger.info(msg)
        queued = True
    except amqp_utils.amqplib_error_types as e:
        if amqp_utils.is_amqplib_connection_error(e):
            # Could not connect / interrupted connection
            queued = False
        # Unknown error mode : don't hide it.
        raise
    finally:
        channel.close()
    return queued


def submit_core(request, oopsid, arch, system_token):
    try:
        # every OOPS will have a SystemIdentifier
        _ = cassandra_schema.OOPS.get(key=oopsid.encode(), column1="SystemIdentifier")
    except DoesNotExist:
        # Due to Cassandra's eventual consistency model, we may receive
        # the core dump before the OOPS has been written to all the
        # nodes. This is acceptable, as we'll just ask the next user
        # for a core dump.
        msg = "No OOPS found for this core dump."
        logger.info(msg)
        metrics.meter("submit_core.no_matching_oops")
        return msg, 400

    # Only accept core files for architectures for which we have retracers,
    # this also won't write weird things like, (md64 or md64, which happened
    # in 2021.
    if arch not in ("amd64", "arm64", "armhf", "i386"):
        return "Unsupported architecture", 400

    message = write_to_swift(request.data, oopsid)
    if not message:
        # If not written to storage then write to log file
        msg = "Failure to write OOPS %s to storage provider" % (oopsid)
        logger.info(msg)
        # Return False and whoopsie will not try and upload it again.
        # However, we'll ask for a core file for a different crash with the
        # same SAS.
        return msg, 500

    queued = write_to_amqp(f"{oopsid}:swift", arch)
    if not queued:
        # If not written to amqp then write to log file
        msg = "Failure to write to amqp retrace queue %s %s" % (arch, message)
        logger.info(msg)
        metrics.meter("failure.unable_to_queue_retracing_request")

    try:
        addr_sig = cassandra_schema.OOPS.get(
            key=oopsid.encode(), column1="StacktraceAddressSignature"
        ).value
    except DoesNotExist:
        addr_sig = ""
    # N.B. a report without an initial StacktraceAddressSignature won't be
    # written to the retracing index which is correct because there isn't a
    # way to identify similar ones without a SAS.
    if addr_sig and queued:
        cassandra_schema.Indexes.create(key=b"retracing", column1=addr_sig, value=b"")

    return oopsid, 200
