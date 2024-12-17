#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright © 2011-2024 Canonical Ltd.
# Authors: Evan Dandrea <evan.dandrea@canonical.com>
#          Brian Murray <brian.murray@canonical.com>
#          Florent 'Skia' Jacquet <florent.jacquet@canonical.com>
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

# stdlib
import amqp
import argparse
import atexit
import datetime
import logging
import os
import re
import shutil
import signal
import socket
import struct
import sys
import tempfile
import traceback
import time
from subprocess import Popen, PIPE

# external libs
from apport import Report

from cassandra.cqlengine import connection
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

# internal libs
from daisy.metrics import get_metrics, record_revno
from daisy.version import version_info as daisy_version_info
from daisy import config
from daisy import utils
from daisy import cassandra_schema
from oopsrepository import config as oopsconfig

apport_version_info = {}
try:
    from apport.version_info import version_info as apport_version_info
except:
    pass


LOGGING_FORMAT = (
    "%(asctime)s:%(process)d:%(thread)d" ":%(levelname)s:%(name)s:%(message)s"
)

_cached_swift = None
_cached_s3 = None
_swift_auth_failure = False

metrics = get_metrics("retracer.%s" % socket.gethostname())


def log(message, level=logging.INFO):
    logging.log(level, message)


def rm_eff(path):
    """Remove ignoring -ENOENT."""
    try:
        os.remove(path)
    except OSError as e:
        if e.errno != 2:
            raise


@atexit.register
def shutdown():
    # if apport crashes / fails this directory may be leftover
    # clean it up so apport can run a second time
    for target in (
        "x86_64-linux-gnu",
        "aarch64-linux-gnu",
        "i686-linux-gnu",
        "armv7l-linux-gnu",
        "ppc64le-linux-gnu",
    ):
        if os.path.exists("/usr/lib/debug/.dwz/%s" % target) and os.path.islink(
            "/usr/lib/debug/.dwz/%s" % target
        ):
            os.unlink("/usr/lib/debug/.dwz/%s" % target)
            log("Removed .dwz symlink for %s" % target)
    log("Shutting down.")
    metrics.meter("shutdown")


def prefix_log_with_amqp_message(func):
    def wrapped(obj, msg):
        try:
            # This is a terrible hack to include the UUID for the core file and
            # OOPS report as well as the storage provider name with the log
            # message.
            format_string = (
                "%(asctime)s:%(process)d:%(thread)d:%(levelname)s"
                ":%(name)s:" + msg.body.decode() + ":%(message)s"
            )
            formatter = logging.Formatter(format_string)
            logging.getLogger().handlers[0].setFormatter(formatter)
            func(obj, msg)
        finally:
            formatter = logging.Formatter(LOGGING_FORMAT)
            logging.getLogger().handlers[0].setFormatter(formatter)

    return wrapped


class ApportException(Exception):
    """Class for exceptions caused by apport retrace"""

    pass


class Retracer:
    def __init__(
        self,
        config_dir,
        sandbox_dir,
        architecture,
        verbose,
        cache_debs,
        use_sandbox,
        cleanup_sandbox,
        cleanup_debs,
        stacktrace_source,
        failed=False,
    ):
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self._stop_now = False
        self._processing_callback = False
        self.setup_cassandra()
        self.config_dir = config_dir
        self.sandbox_dir = sandbox_dir
        self.verbose = verbose
        self.stacktrace_source = stacktrace_source
        self.architecture = architecture
        self.failed = failed
        self.connection = None
        self.channel = None
        # A mapping of release names to temporary sandbox and cache
        # directories, so that we can remove them at the end of the run.
        # TODO: we should create a single temporary directory that all of these
        # live under, saving the multiple calls to atexit.register.
        self._sandboxes = {}
        # The time we were last able to talk to the AMQP server.
        self._lost_connection = None
        self.cache_debs = cache_debs
        self.use_sandbox = use_sandbox
        self.cleanup_sandbox = cleanup_sandbox
        self.cleanup_debs = cleanup_debs

        # determine path of gdb
        gdb_which = Popen(["which", "gdb"], stdout=PIPE, universal_newlines=True)
        self.gdb_path = gdb_which.communicate()[0].strip()

        # determine path of apport-retrace
        which = Popen(["which", "apport-retrace"], stdout=PIPE, universal_newlines=True)
        self.apport_retrace_path = which.communicate()[0].strip()

        m = "Cannot find apport-retrace in $PATH (%s)" % os.environ.get("PATH")
        assert which.returncode == 0, m

    def exit_gracefully(self, signal, frame):
        # Set a flag so that we can give apport-retrace a chance to finish.
        log("Received SIGTERM")
        # 2018-03-14 do something with the core file
        # I think we'd need to make msg and oops_ids globals
        self._stop_now = True
        if not self._processing_callback:
            if self.connection:
                self.connection.close()
            if self.channel:
                self.channel.close()
            sys.exit()

    def setup_cassandra(self):
        os.environ["OOPS_KEYSPACE"] = config.cassandra_keyspace
        self.oops_config = oopsconfig.get_config()
        auth_provider = PlainTextAuthProvider(
            username=config.cassandra_username, password=config.cassandra_password
        )
        connection.setup(config.cassandra_hosts, "crashdb", auth_provider=auth_provider)
        self.oops_config["host"] = config.cassandra_hosts
        self.oops_config["username"] = config.cassandra_username
        self.oops_config["password"] = config.cassandra_password

    def listen(self):
        if self.failed:
            retrace = "failed_retrace_%s"
        else:
            retrace = "retrace_%s"
        retrace = retrace % self.architecture
        try:
            if config.amqp_username and config.amqp_password:
                self.connection = amqp.Connection(
                    host=config.amqp_host,
                    userid=config.amqp_username,
                    password=config.amqp_password,
                )
            else:
                self.connection = amqp.Connection(host=config.amqp_host)
            self.connection.connect()
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=retrace, durable=True, auto_delete=False)
            self.channel.basic_qos(0, 1, False)
            log("Waiting for messages. ^C to exit.")
            self.run_forever(queue=retrace)
        finally:
            if self.connection:
                self.connection.close()
            if self.channel:
                self.channel.close()

    def run_forever(self, queue):
        tag = self.channel.basic_consume(callback=self.callback, queue=queue)
        try:
            while (
                not self._lost_connection
                or time.time() < self._lost_connection + 120
                or self._stop_now
                and not self._processing_callback
            ):
                try:
                    self.connection.drain_events()
                except (socket.error, IOError) as e:
                    is_amqplib_ioerror = type(e) is IOError and e.args == (
                        "Socket error",
                    )
                    amqplib_conn_errors = (socket.error, amqp.ConnectionError)
                    is_amqplib_conn_error = isinstance(e, amqplib_conn_errors)
                    if is_amqplib_conn_error or is_amqplib_ioerror:
                        self._lost_connection = time.time()
                        log("lost connection to Rabbit")
                        metrics.meter("lost_rabbit_connection")
                        # Don't probe immediately, give the network/process
                        # time to come back.
                        time.sleep(0.1)
                    else:
                        raise
            if self._stop_now and not self._processing_callback:
                log("Exiting due to SIGTERM.")
            log("Rabbit did not reappear quickly enough.")
        except KeyboardInterrupt:
            pass
        if self.channel and self.channel.is_open:
            self.channel.basic_cancel(tag)

    def update_retrace_stats(self, release, day_key, retracing_time, result):
        """
        release: the distribution release, ex. 'Ubuntu 12.04'
        day_key: the date as a YYYYMMDD string.
        retracing_time: the amount of time it took to retrace.
        result: the end result of the retracing process.
        """
        # This is kept around for legacy reasons. The integration tests
        # currently depend on this being exposed in the API.
        status = result
        # Increment the counters. This will create the rows if they don't exist yet.
        cassandra_schema.RetraceStats(
            key=day_key.encode(), column1="%s:%s" % (release, status)
        ).update(value=1)
        cassandra_schema.RetraceStats(
            key=day_key.encode(),
            column1="%s:%s:%s" % (release, self.architecture, status),
        ).update(value=1)

        # Compute the cumulative moving average
        mean_key = "%s:%s:%s" % (day_key, release, self.architecture)
        count_key = "%s:count" % mean_key
        try:
            mean = cassandra_schema.Indexes.get_as_dict(
                key=b"mean_retracing_time",
                column1__in=[
                    mean_key,
                    count_key,
                ],
            )
            # keep those two hex values to display in logging when something goes wrong
            mean[mean_key + "_hex"] = mean[mean_key]
            mean[count_key + "_hex"] = mean[count_key]

            mean[mean_key] = struct.unpack("!f", mean[mean_key])[0]
            mean[count_key] = int.from_bytes(mean[count_key])
        except cassandra_schema.DoesNotExist:
            mean = {mean_key: 0.0, count_key: 0}

        new_mean = float(
            (retracing_time + mean[count_key] * mean[mean_key]) / (mean[count_key] + 1)
        )
        mean[mean_key] = new_mean
        mean[count_key] += 1
        try:
            cassandra_schema.Indexes.objects.create(
                key=b"mean_retracing_time",
                column1=mean_key,
                value=struct.pack("!f", mean[mean_key]),
            )
            cassandra_schema.Indexes.objects.create(
                key=b"mean_retracing_time",
                column1=count_key,
                value=struct.pack("!i", mean[count_key]),
            )
        except struct.error as e:
            log(f"TODO SKIA - Issue packing data: {repr(e)}")
            log(f"TODO SKIA - data: {mean}")

        # Report this into statsd as well.
        prefix = "timings.retracing"
        if release:
            m = "%s.all_releases.%s.%s" % (prefix, self.architecture, status)
            metrics.timing(m, retracing_time)
            m = "%s.%s.all_architectures.%s" % (prefix, release, status)
            metrics.timing(m, retracing_time)
            m = "%s.%s.%s.%s" % (prefix, release, self.architecture, status)
            metrics.timing(m, retracing_time)
        m = "%s.all.all_architectures.%s" % (prefix, status)
        metrics.timing(m, retracing_time)
        m = "%s.%s.all.%s" % (prefix, self.architecture, status)
        metrics.timing(m, retracing_time)

    def setup_cache(self, sandbox_dir, release):
        if release in self._sandboxes:
            return self._sandboxes[release]
        sandbox_release = os.path.join(sandbox_dir, release)
        if not os.path.exists(sandbox_release):
            os.makedirs(sandbox_release)
        instance_sandbox = tempfile.mkdtemp(prefix="cache-", dir=sandbox_release)
        atexit.register(shutil.rmtree, instance_sandbox)
        # Write a pid file so that if we have to wipe out a cache that has
        # grown too large we can stop the retracer responsible for it before
        # doing so.
        with open(os.path.join(instance_sandbox, "pid"), "w") as fp:
            fp.write("%d" % os.getpid())
        sandbox = None
        if self.use_sandbox:
            sandbox = os.path.join(instance_sandbox, "sandbox")
            os.mkdir(sandbox)
        cache = None
        if self.cache_debs:
            cache = os.path.join(instance_sandbox, "cache")
            os.mkdir(cache)
        self._sandboxes[release] = (sandbox, cache)
        return self._sandboxes[release]

    def move_to_failed_queue(self, msg):
        if self.failed:
            # It failed its 2nd retrace attempt, admit defeat and don't try
            # again.
            self.processed(msg)
            return

        # We've processed this. Delete it off the MQ.
        msg.channel.basic_ack(msg.delivery_tag)
        # We don't call self.processed here because that would remove the core
        # file from the storage provider, and we want to retain it.

        # Add it to the failed to retrace queue.
        queue = "failed_retrace_%s" % self.architecture
        msg.channel.queue_declare(queue=queue, durable=True, auto_delete=False)
        body = amqp.Message(msg.body)
        # Persistent
        body.properties["delivery_mode"] = 2
        msg.channel.basic_publish(body, exchange="", routing_key=queue)

    def failed_to_process(self, msg, oops_id, old=False):
        # Try to remove the core file from the storage provider
        parts = msg.body.decode().split(":", 1)
        oops_id = None
        oops_id, provider = parts
        removed = self.remove(*parts)
        if removed:
            # We've processed this. Delete it off the MQ.
            msg.channel.basic_ack(msg.delivery_tag)
            self.update_time_to_retrace(msg)
        # Removing the core file failed in the processing phase, so requeue
        # the crash unless it is an old OOPS then don't requeue it.
        elif not removed and not old:
            log("Requeued failed to process OOPS (%s)" % oops_id)
            self.requeue(msg, oops_id)
        # It is old so we should just ack the request to retrace it.
        elif not removed and old:
            log("Ack'ing message about old missing core.")
            msg.channel.basic_ack(msg.delivery_tag)
            metrics.meter("retrace.failure.old_missing_core")
        # Also remove it from the retracing index, if we haven't already.
        try:
            addr_sig = cassandra_schema.OOPS.objects.get(
                key=oops_id, column1="StacktraceAddressSignature"
            )["value"]
            cassandra_schema.Indexes.objects.filter(
                key=b"retracing", column1=addr_sig
            ).delete()
        except cassandra_schema.DoesNotExist as e:
            log(
                "Could not remove from the retracing row (%s) (%s):"
                % (oops_id, repr(e))
            )

    def write_swift_bucket_to_disk(self, key, provider_data):
        global _cached_swift
        global _swift_auth_failure
        import swiftclient

        opts = {
            "tenant_name": provider_data["os_tenant_name"],
            "region_name": provider_data["os_region_name"],
        }
        if not _cached_swift:
            _cached_swift = swiftclient.client.Connection(
                provider_data["os_auth_url"],
                provider_data["os_username"],
                provider_data["os_password"],
                os_options=opts,
                auth_version="3.0",
            )
        if self.verbose:
            log("swift token: %s" % str(_cached_swift.token))
        fmt = "-{}.{}.oopsid".format(provider_data["type"], key)
        fd, path = tempfile.mkstemp(fmt)
        os.close(fd)
        bucket = provider_data["bucket"]
        try:
            _cached_swift.http_conn = None
            headers, body = _cached_swift.get_object(bucket, key, resp_chunk_size=65536)
            with open(path, "wb") as fp:
                for chunk in body:
                    fp.write(chunk)
            return path
        except swiftclient.client.ClientException as e:
            if "Unauthorized" in str(e):
                metrics.meter("swift_client_exception.auth_failure")
                log("Authorization failure connecting to swift.")
                _swift_auth_failure = True
            elif "404 Not Found" in str(e):
                return "Missing"
            else:
                metrics.meter("swift_client_exception")
                log("Could not retrieve %s (swift):" % key)
            log(traceback.format_exc())
            # This will still exist if we were partway through a write.
            rm_eff(path)
            return None

    def remove_from_swift(self, key, provider_data):
        global _cached_swift
        global _swift_auth_failure
        import swiftclient

        opts = {
            "tenant_name": provider_data["os_tenant_name"],
            "region_name": provider_data["os_region_name"],
        }
        # test that the connection to swift still works
        if _cached_swift:
            try:
                _cached_swift.get_account()
            except swiftclient.client.ClientException as e:
                if "Unauthorized" in str(e):
                    log("Authorization failure getting account info")
                    _cached_swift = ""
        if not _cached_swift:
            _cached_swift = swiftclient.client.Connection(
                provider_data["os_auth_url"],
                provider_data["os_username"],
                provider_data["os_password"],
                os_options=opts,
                auth_version="3.0",
            )
        if self.verbose:
            log("swift token: %s" % str(_cached_swift.token))
        bucket = provider_data["bucket"]
        try:
            _cached_swift.http_conn = None
            _cached_swift.delete_object(bucket, key)
        # 404s are handled when we write the bucket to disk
        except swiftclient.client.ClientException as e:
            if "Unauthorized" in str(e):
                metrics.meter("swift_client_exception.auth_failure")
                log("Authorization failure connecting to swift.")
                log(traceback.format_exc())
                # if there is a failure to receive and a failure to delete
                # stop the retracing process
                if _swift_auth_failure:
                    log("Two swift auth failures, stopping.")
                    sys.exit(1)
                _swift_auth_failure = True
            else:
                log("Could not remove %s (swift):" % key)
                log(traceback.format_exc())
                metrics.meter("swift_delete_error")
                return False
        return True

    def write_s3_bucket_to_disk(self, key, provider_data):
        global _cached_s3
        from boto.s3.connection import S3Connection
        from boto.exception import S3ResponseError

        if not _cached_s3:
            _cached_s3 = S3Connection(
                aws_access_key_id=provider_data["aws_access_key"],
                aws_secret_access_key=provider_data["aws_secret_key"],
                host=provider_data["host"],
            )
        try:
            bucket = _cached_s3.get_bucket(provider_data["bucket"])
            key = bucket.get_key(key)
        except S3ResponseError:
            log("Could not retrieve %s (s3):" % key)
            log(traceback.format_exc())
            return None
        fmt = "-{}.{}.oopsid".format(provider_data["type"], key)
        fd, path = tempfile.mkstemp(fmt)
        os.close(fd)
        with open(path, "wb") as fp:
            for data in key:
                # 8K at a time.
                fp.write(data)
        return path

    def remove_from_s3(self, key, provider_data):
        global _cached_s3
        from boto.s3.connection import S3Connection
        from boto.exception import S3ResponseError

        try:
            if not _cached_s3:
                _cached_s3 = S3Connection(
                    aws_access_key_id=provider_data["aws_access_key"],
                    aws_secret_access_key=provider_data["aws_secret_key"],
                    host=provider_data["host"],
                )
            bucket = _cached_s3.get_bucket(provider_data["bucket"])
            key = bucket.get_key(key)
            key.delete()
        except S3ResponseError:
            log("Could not remove %s (s3):" % key)
            log(traceback.format_exc())
            return False
        return True

    def write_local_to_disk(self, key, provider_data):
        path = os.path.join(provider_data["path"], key)
        fmt = "-{}.{}.oopsid".format(provider_data["type"], key)
        fd, new_path = tempfile.mkstemp(fmt)
        os.close(fd)
        if not os.path.exists(path):
            return None
        else:
            shutil.copyfile(path, new_path)
            return new_path

    def remove_from_local(self, key, provider_data):
        path = os.path.join(provider_data["path"], key)
        rm_eff(path)
        return True

    def write_bucket_to_disk(self, oops_id, provider):
        path = ""
        cs = getattr(config, "core_storage", "")
        if not cs:
            log("core_storage not set.")
            sys.exit(1)
        provider_data = cs[provider]
        t = provider_data["type"]
        if t == "swift":
            path = self.write_swift_bucket_to_disk(oops_id, provider_data)
        elif t == "s3":
            path = self.write_s3_bucket_to_disk(oops_id, provider_data)
        elif t == "local":
            path = self.write_local_to_disk(oops_id, provider_data)
        return path

    def remove(self, oops_id, provider):
        cs = getattr(config, "core_storage", "")
        if not cs:
            log("core_storage not set.")
            sys.exit(1)
        provider_data = cs[provider]
        t = provider_data["type"]
        if t == "swift":
            removed = self.remove_from_swift(oops_id, provider_data)
        elif t == "s3":
            removed = self.remove_from_s3(oops_id, provider_data)
        elif t == "local":
            removed = self.remove_from_local(oops_id, provider_data)
        if removed:
            return True
        return False

    def save_crash(self, failure_storage, report, oops_id, core_file):
        log("Saved OOPS %s for manual investigation." % oops_id)
        # create a new crash with the CoreDump for investigation
        report["CoreDump"] = (core_file,)
        failed_crash = "%s/%s.crash" % (failure_storage, oops_id)
        with open(failed_crash, "wb") as fp:
            report.write(fp)

    @prefix_log_with_amqp_message
    def callback(self, msg):
        self._processing_callback = True
        log("Processing.")
        parts = msg.body.decode().split(":", 1)
        oops_id, provider = parts
        try:
            col = cassandra_schema.OOPS.get_as_dict(key=oops_id.encode())
        except cassandra_schema.DoesNotExist:
            # We do not have enough information at this point to be able to
            # remove this from the retracing row in the Indexes CF. Throw it
            # back on the queue and hope that eventual consistency works its
            # magic by then.
            log("Unable to find in OOPS CF.")
            self.requeue(msg, oops_id)

            metrics.meter("could_not_find_oops")
            return
        # There are some items still in amqp queue that have already been
        # retraced, check for this and ack the message.
        # N.B.: This only works in some cases because we don't mark a report as
        # having been retraced e.g. there is no Retrace column in keys
        if "RetraceFailureReason" in list(
            col.keys()
        ) or "RetraceOutdatedPackages" in list(col.keys()):
            log("Ack'ing already retraced OOPS.")
            msg.channel.basic_ack(msg.delivery_tag)
            # 2016-05-19 - this failed to delete cores and ack'ing of msgs
            # Call processed so that we also try to remove the core file
            # self.processed(msg)
            return

        # Check to see if there is an UnreportableReason so we can log more
        # information about failures to retrace.
        unreportable_reason = ""
        if "UnreportableReason" in list(col.keys()):
            unreportable_reason = col["UnreportableReason"]

        path = self.write_bucket_to_disk(*parts)

        if path == "Missing":
            log("Ack'ing OOPS with missing core file.")
            msg.channel.basic_ack(msg.delivery_tag)
            return
        if not path or not os.path.exists(path):
            log("Could not find %s" % path)
            self.failed_to_process(msg, oops_id)
            return

        core_file = "%s.core" % path
        with open(core_file, "wb") as fp:
            log("Decompressing to %s" % core_file)
            p1 = Popen(["base64", "-d", path], stdout=PIPE)
            # Set stderr to PIPE so we get output in the result tuple.
            p2 = Popen(["zcat"], stdin=p1.stdout, stdout=fp, stderr=PIPE)
            ret = p2.communicate()
        rm_eff(path)

        if p2.returncode != 0:
            log("Error processing %s:" % path)
            if unreportable_reason:
                log("UnreportableReason is: %s" % unreportable_reason)
            if ret[1]:
                for line in ret[1].splitlines():
                    log(line)
            # We couldn't decompress this, so there's no value in trying again.
            self.processed(msg)
            # probably incomplete cores from armhf?
            metrics.meter("retrace.failed")
            metrics.meter("retrace.failed.%s" % self.architecture)
            metrics.meter("retrace.failure.decompression")
            metrics.meter("retrace.failure.decompression.%s" % self.architecture)
            rm_eff(core_file)
            return
        # confirm that gdb thinks the core file is good
        gdb_cmd = [self.gdb_path, "--batch", "--ex", "target core %s" % core_file]
        proc = Popen(gdb_cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        (out, err) = proc.communicate()
        if "is truncated: expected core file size" in err or "not a core dump" in err:
            # Not a core file, there's no value in trying again.
            self.processed(msg)
            log("Not a core dump per gdb.")
            if unreportable_reason:
                log("UnreportableReason is: %s" % unreportable_reason)
            metrics.meter("retrace.failed")
            metrics.meter("retrace.failed.%s" % self.architecture)
            metrics.meter("retrace.failure.gdb_core_check")
            metrics.meter("retrace.failure.gdb_core_check.%s" % self.architecture)
            rm_eff(core_file)
            return

        report = Report()

        for k in col:
            try:
                report[k] = col[k]
            except (AssertionError, ValueError):
                # apport raises an ValueError if a key is invalid
                # e.g. /usr/bin/media-hub-server became a key somehow,
                # and this doesn't need to be part of the report used
                # for retracing
                continue

        # these will not change after retracing
        architecture = report.get("Architecture", "")
        release = report.get("DistroRelease", "")
        bad = "[^-a-zA-Z0-9_.() ]+"
        retraceable = utils.retraceable_release(release)
        if not retraceable:
            metrics.meter("retrace.failed.notretraceable")
            if release in utils.EOL_RELEASES:
                metrics.meter("retrace.failed.eolrelease")
                log("Not retraced due to EoL release: %s" % release)
        package = report.get("Package", "")
        # there will not be a debug symbol version of the package
        if not utils.retraceable_package(package):
            log("Not retraced due to foreign origin.")
            if unreportable_reason:
                log("UnreportableReason is: %s" % unreportable_reason)
            metrics.meter("retrace.failed.foreign")
            retraceable = False
        # srcpackage = report.get('SourcePackage', '')
        # if srcpackage in ['kodi', 'mysql-workbench'] and release == 'Ubuntu 18.04':
        # 2018-06-13 gdb is hanging trying to retrace these so put them at
        # the end of the line.
        #    log('Requeueing an Ubuntu 18.04 %s crash.' % srcpackage)
        #    self.requeue(msg, oops_id)
        #    rm_eff(core_file)
        #    return

        invalid = re.search(bad, release) or len(release) > 1024
        if invalid:
            metrics.meter("retrace.failed.invalid")
        if not release or invalid or not retraceable:
            self.processed(msg)
            rm_eff(core_file)
            return

        report_path = "%s.crash" % path
        with open(report_path, "wb") as fp:
            report.write(fp)

        try:
            retrace_msg = "Retracing {}".format(msg.body.decode())
            sandbox, cache = self.setup_cache(self.sandbox_dir, release)
            day_key = time.strftime("%Y%m%d", time.gmtime())

            retracing_start_time = time.time()
            # the easiest way to test not using a sandbox is to make it another
            # command line option like don't use sandbox even though we will
            # provide it on the cli
            cmd = [
                "python3",
                self.apport_retrace_path,
                report_path,
                "--core-file",
                core_file,
                "--remove-core",
                "--sandbox",
                self.config_dir,
                "--gdb-sandbox",
                "--output",
                "%s.new" % report_path,
            ]
            if sandbox:
                retrace_msg += " with sandbox-dir %s" % sandbox
                cmd.extend(["--sandbox-dir", sandbox])
            if cache:
                retrace_msg += " with cache %s" % cache
                cmd.extend(["-C", cache])
            if not self.stacktrace_source:
                cmd.extend(["--no-stacktrace-source"])
            if self.verbose:
                cmd.append("-v")
            log(retrace_msg)
            # use our own crashdb config with all supported architectures
            env = os.environ.copy()
            env["APPORT_CRASHDB_CONF"] = os.path.join(self.config_dir, "crashdb.conf")
            http_proxy = env.get("retracer_http_proxy")
            if http_proxy:
                env.update({"http_proxy": http_proxy})
            proc = Popen(
                cmd,
                env=env,
                stdout=PIPE,
                stderr=PIPE,
                universal_newlines=True,
                preexec_fn=os.setpgrp,
            )
            out, err = proc.communicate()
        except:
            rm_eff("%s.new" % report_path)
            log("Failure in retrace set up for {}".format(msg.body))
            log(traceback.format_exc())
            metrics.meter("retrace.failed")
            metrics.meter("retrace.failed.%s" % release)
            metrics.meter("retrace.failed.%s" % architecture)
            metrics.meter("retrace.failed.%s.%s" % (release, architecture))
            metrics.meter("retrace.failed.to_setup")
            metrics.meter("retrace.failed.to_setup.%s" % release)
            metrics.meter("retrace.failed.to_setup.%s" % architecture)
            metrics.meter("retrace.failed.to_setup.%s.%s" % (release, architecture))
            raise
        finally:
            if sandbox and self.cleanup_sandbox:
                log("Removing %s" % sandbox)
                shutil.rmtree(sandbox)
                os.mkdir(sandbox)
            if cache and self.cleanup_debs:
                log("Removing %s" % cache)
                shutil.rmtree(cache)
                os.mkdir(cache)
            rm_eff(report_path)

        try:
            if proc.returncode != 0:
                give_up = False
                retry = False
                retrace_result = ""
                if proc.returncode == 1:
                    # Package download errors return 1
                    log("Apport's return code was 1.")
                    # Log the error from apport
                    for std in (out, err):
                        for line in std.splitlines():
                            log(line)
                            # this happens for binaries from packages not in Ubuntu
                            if "Cannot find package which ships ExecutablePath" in line:
                                give_up = True
                                retrace_result = "missing_execpath"
                                break
                            if (
                                "Cannot find package which ships InterpreterPath"
                                in line
                            ):
                                give_up = True
                                retrace_result = "missing_intpath"
                                break
                            if "failed with exit code -9" in line:
                                metrics.meter("retrace.failed.gdb_failure.minus_nine")
                                if failure_storage:
                                    self.save_crash(
                                        failure_storage, report, oops_id, core_file
                                    )
                                give_up = True
                                retrace_result = "gdb_crash"
                                break
                            if "failed with exit code -11" in line:
                                metrics.meter("retrace.failed.gdb_failure.minus_eleven")
                                if failure_storage:
                                    self.save_crash(
                                        failure_storage, report, oops_id, core_file
                                    )
                                give_up = True
                                retrace_result = "gdb_crash"
                                break
                            if "Package download error, try again later" in line:
                                retry = True
                                break
                            # probably due to network errors
                            if "W:GPG error:" in line:
                                retry = True
                                break
                            # probably due to network errors
                            if "index files failed to download." in line:
                                retry = True
                                break
                            # ddeb server could be updating
                            if "Mirror sync in progress" in line:
                                retry = True
                                break
                            # ddeb server in a sad state
                            if "does not have a Release file" in line:
                                retry = True
                                break
                            # ddeb server in a sad state
                            if "Release' is not signed" in line:
                                retry = True
                                break
                    if retry:
                        log("Will retry (%s) due to a transient error." % oops_id)
                        self.requeue(msg, oops_id)
                        # don't record it as a failure in the metrics as it is
                        # going to be retried
                        rm_eff("%s.new" % report_path)
                        # return immediately to prevent moving the crash to
                        # the failed queue
                        self._processing_callback = False
                        return
                elif proc.returncode == -15:
                    log("apport-retrace was killed by retracer restart.")
                    self._processing_callback = False
                    return
                # apport-retrace will exit 0 even on a failed retrace unless
                # something has gone wrong at a lower level, as was the case
                # when python-apt bailed out on invalid sources.list files.
                # Fail hard so we do not incorrectly write a lot of retraces to
                # the database as failures.
                retracing_time = time.time() - retracing_start_time
                invalid_core = False
                for std in (out, err):
                    for line in std.splitlines():
                        # don't log what we've already logged
                        if not give_up and not retry:
                            log(line)
                        if "Invalid core dump" in line:
                            invalid_core = True
                            break
                        # crash file may have been cleaned up from underneath
                        # us by retracer restart script
                        # elif "is neither an existing" in line:
                        #    cfile = line.split(" ")[1].strip('"')
                        #    if not os.path.exists(cfile):
                        #        log("Will retry this oops later.")
                        #        return
                m = "Retrace failed (%i), %s"
                action = "leaving as failed."
                if give_up:
                    cassandra_schema.OOPS.objects.create(
                        key=oops_id.encode(), column1="RetraceStatus", value="Failure"
                    )
                    # we don't want to see this OOPS again so process it
                    self.processed(msg)
                else:
                    self.move_to_failed_queue(msg)
                    if not self.failed:
                        action = "moving to failed queue."
                log(m % (proc.returncode, action))
                if invalid_core:
                    if unreportable_reason:
                        log("UnreportableReason is: %s" % unreportable_reason)
                    # these should not be reported LP: #1354571 so record
                    # apport version
                    apport_vers = report.get("ApportVersion", "")
                    metrics.meter("retrace.failed.invalid_core")
                    metrics.meter("retrace.failed.invalid_core.%s" % release)
                    metrics.meter("retrace.failed.invalid_core.%s" % architecture)
                    metrics.meter(
                        "retrace.failed.invalid_core.%s.%s" % (release, architecture)
                    )
                    if apport_vers:
                        metrics.meter(
                            "retrace.failed.invalid_core.%s.%s"
                            % (release, apport_vers.replace(".", "_"))
                        )
                    retrace_result = "invalid_core"
                # Remove the SAS from the retracing index so that we ask for
                # another core
                sas = report.get("StacktraceAddressSignature", "")
                if sas:
                    cassandra_schema.Indexes.objects.filter(
                        key=b"retracing", column1=sas
                    ).delete()
                self.update_retrace_stats(
                    release, day_key, retracing_time, result=retrace_result
                )
                metrics.meter("retrace.failed")
                metrics.meter("retrace.failed.%s" % release)
                metrics.meter("retrace.failed.%s" % architecture)
                metrics.meter("retrace.failed.%s.%s" % (release, architecture))
                if failure_storage:
                    self.save_crash(failure_storage, report, oops_id, core_file)
                rm_eff("%s.new" % report_path)
                # TODO 2024-12-16: Skia: let's see what to do with that later,
                # but for now we don't want the retracer to choke on this.
                # raise ApportException(err)
                self._processing_callback = False
                return

            retracing_time = time.time() - retracing_start_time

            if not os.path.exists("%s.new" % report_path):
                log("%s.new did not exist." % report_path)
                metrics.meter("retrace.missing.retraced_crash_file")
                self.failed_to_process(msg, oops_id)
                metrics.meter("retrace.failed")
                metrics.meter("retrace.failed.%s" % release)
                metrics.meter("retrace.failed.%s" % architecture)
                metrics.meter("retrace.failed.%s.%s" % (release, architecture))
                self._processing_callback = False
                return

            log("Writing back to Cassandra")
            report = Report()
            # ran into MemoryError loading retraced report with CoreDump
            with open("%s.new" % report_path, "rb") as fp:
                report.load(fp)

            crash_signature = report.crash_signature()
            stacktrace_addr_sig = report.get("StacktraceAddressSignature", "")
            # col contains information about the report before retracing
            original_sas = col.get("StacktraceAddressSignature", "")

            missing_dbgsym_pkg = False
            if "RetraceOutdatedPackages" in report:
                if "no debug symbol package" in report["RetraceOutdatedPackages"]:
                    missing_dbgsym_pkg = True
            if not crash_signature:
                log("Apport did not return a crash_signature.")
                cassandra_schema.OOPS.objects.create(
                    key=oops_id.encode(), column1="RetraceStatus", value="Failure"
                )
                if unreportable_reason:
                    log("UnreportableReason is: %s" % unreportable_reason)
                metrics.meter("retrace.missing.crash_signature")
                metrics.meter("retrace.missing.%s.crash_signature" % architecture)
                metrics.meter("retrace.missing.%s.crash_signature" % release)
                metrics.meter(
                    "retrace.missing.%s.%s.crash_signature" % (release, architecture)
                )
                if missing_dbgsym_pkg:
                    metrics.meter(
                        "retrace.missing.crash_signature. \
                                   no_dbgsym_pkg"
                    )
                    metrics.meter(
                        "retrace.missing.%s.crash_signature. \
                                   no_dbgsym_pkg"
                        % release
                    )
                if "StacktraceTop" in report:
                    log("StacktraceTop:")
                    stacktracetop = report["StacktraceTop"]
                    for line in stacktracetop.splitlines():
                        log(line)
                    # If the StacktraceTop is completely useless but we had
                    # a SAS in the original report and nothing predicts a
                    # failure we should retry retracing the crash.
                    # StacktraceTop can have a variable number of lines.
                    if (
                        set(stacktracetop.splitlines()) == {"?? ()"}
                        and original_sas
                        and not unreportable_reason
                        and not missing_dbgsym_pkg
                    ):
                        metrics.meter("retrace.missing.crash_signature.apport_issue")
                        count = int(col.get("RetraceAttempts", 0))
                        # only requeue this failure type 2 times
                        if count < 2:
                            count += 1
                            log("Requeueing a possible apport failure (#%s)." % count)
                            cassandra_schema.OOPS.objects.create(
                                key=oops_id.encode(),
                                column1="RetraceAttempts",
                                value="%s" % count,
                            )
                            self.requeue(msg, oops_id)
                            # don't record it as a failure in the metrics as it is
                            # going to be retried
                            rm_eff("%s.new" % report_path)
                            # return immediately to prevent moving the crash to
                            # the failed queue
                            self._processing_callback = False
                            return
                        else:
                            log("Gave up requeueing after %s attempts." % count)
                if architecture == "armhf" and "RetraceOutdatedPackages" not in report:
                    if failure_storage:
                        self.save_crash(failure_storage, report, oops_id, core_file)

            if stacktrace_addr_sig and not original_sas:
                # if the OOPS doesn't already have a SAS add one
                cassandra_schema.OOPS.objects.create(
                    key=oops_id.encode(),
                    column1="StacktraceAddressSignature",
                    value=stacktrace_addr_sig,
                )
                cassandra_schema.OOPS.objects.create(
                    key=oops_id.encode(), column1="RetraceStatus", value="Success"
                )
            else:
                metrics.meter("retrace.missing.stacktrace_address_signature")
                metrics.meter(
                    "retrace.missing.%s.stacktrace_address_signature" % architecture
                )
                metrics.meter(
                    "retrace.missing.%s.stacktrace_address_signature" % release
                )
                metrics.meter(
                    "retrace.missing.%s.%s.stacktrace_address_signature"
                    % (release, architecture)
                )
                cassandra_schema.OOPS.objects.create(
                    key=oops_id.encode(), column1="RetraceStatus", value="Failure"
                )

            # Use the unretraced report's SAS for the index and stacktrace_cf,
            # otherwise use the one from the retraced report as apport / gdb
            # may improve
            if original_sas:
                stacktrace_addr_sig = original_sas

            crash_signature = utils.format_crash_signature(crash_signature)

            # only consider it a successful retrace if there is a Stacktrace
            # in the retraced report LP: #1321386
            if crash_signature and stacktrace_addr_sig and "Stacktrace" in report:
                if "CoreDump" in report:
                    report.pop("CoreDump")
                for k, v in report.items():
                    cassandra_schema.Stacktrace.objects.create(
                        key=stacktrace_addr_sig.encode(), column1=k, value=v
                    )
                args = (release, day_key, retracing_time, "success")
                self.update_retrace_stats(*args)
                cassandra_schema.OOPS.objects.create(
                    key=oops_id.encode(), column1="RetraceStatus", value="Success"
                )
                log("Successfully retraced.")
                metrics.meter("retrace.success")
                metrics.meter("retrace.success.%s" % release)
                metrics.meter("retrace.success.%s" % architecture)
                metrics.meter("retrace.success.%s.%s" % (release, architecture))
                # for having a total count of missing ddebs log outdated
                # packages for successful retraces too
                if "RetraceOutdatedPackages" in report:
                    log("RetraceOutdatedPackages:")
                    for line in report["RetraceOutdatedPackages"].splitlines():
                        log("%s (%s)" % (line, release))
            else:
                # we aren't adding the report back to the stacktrace_cf so put
                # the CoreDump back in the report in case we save it
                report["CoreDump"] = (core_file,)
                if "Stacktrace" not in report and crash_signature:
                    log("Stacktrace not in retraced report with a crash_sig.")
                    if unreportable_reason:
                        log("UnreportableReason is: %s" % unreportable_reason)
                    metrics.meter("retrace.missing.stacktrace")
                    metrics.meter("retrace.missing.%s.stacktrace" % architecture)
                    metrics.meter("retrace.missing.%s.stacktrace" % release)
                    metrics.meter(
                        "retrace.missing.%s.%s.stacktrace" % (release, architecture)
                    )
                    if failure_storage:
                        self.save_crash(failure_storage, report, oops_id, core_file)

                cassandra_schema.OOPS.objects.create(
                    key=oops_id.encode(), column1="RetraceStatus", value="Failure"
                )
                # Given that we do not as yet keep debugging symbols around for
                # every package version ever released, it's worth knowing the
                # extent of the problem. If we ever decide to keep debugging
                # symbols for every package version, we can reprocess these
                # with a map/reduce job.
                log("Could not retrace.")

                if stacktrace_addr_sig:
                    crash_signature = "failed:%s" % utils.format_crash_signature(
                        stacktrace_addr_sig
                    )
                else:
                    log("Retraced report missing stacktrace_addr_sig.")
                    if unreportable_reason:
                        log("UnreportableReason is: %s" % unreportable_reason)
                    metrics.meter("retrace.missing.stacktrace_addr_sig")
                    metrics.meter(
                        "retrace.missing.%s.stacktrace_addr_sig" % architecture
                    )
                    metrics.meter("retrace.missing.%s.stacktrace_addr_sig" % release)
                    metrics.meter(
                        "retrace.missing.%s.%s.stacktrace_addr_sig"
                        % (release, architecture)
                    )
                    if failure_storage:
                        self.save_crash(failure_storage, report, oops_id, core_file)

                if "Stacktrace" not in report:
                    failure_reason = "No stacktrace after retracing"
                    log("Retraced report missing Stacktrace.")
                    if unreportable_reason:
                        log("UnreportableReason is: %s" % unreportable_reason)
                else:
                    failure_reason = "No crash signature after retracing"
                    if unreportable_reason:
                        log("UnreportableReason is: %s" % unreportable_reason)

                if "RetraceOutdatedPackages" in report:
                    # these counters will overlap with outdated_packages but
                    # that is okay
                    if missing_dbgsym_pkg:
                        metrics.meter("retrace.failure.missing_dbgsym")
                        metrics.meter("retrace.failure.%s.missing_dbgsym" % release)
                    outdated_pkgs = []
                    missing_ddebs = []
                    log("RetraceOutdatedPackages:")
                    for line in report["RetraceOutdatedPackages"].splitlines():
                        if "outdated debug symbol" in line:
                            outdated_pkgs.append(line.split(" ")[0])
                        if "no debug symbol" in line:
                            missing_ddebs.append(line.split(" ")[-1])
                        log("%s (%s)" % (line, release))
                    if architecture == "armhf" and missing_ddebs and not outdated_pkgs:
                        if failure_storage:
                            self.save_crash(failure_storage, report, oops_id, core_file)
                    if not outdated_pkgs:
                        failure_reason += " and missing ddebs."
                    else:
                        failure_reason += " and outdated packages."
                    cassandra_schema.OOPS.objects.create(
                        key=oops_id.encode(),
                        column1="RetraceFailureReason",
                        value=failure_reason,
                    )
                    if outdated_pkgs:
                        outdated_pkg_count = len(outdated_pkgs)
                        outdated_pkgs.sort()
                        cassandra_schema.OOPS.objects.create(
                            key=oops_id.encode(),
                            column1="RetraceFailureOutdatedPackages",
                            value=" ".join(outdated_pkgs),
                        )
                    else:
                        outdated_pkgs = ""
                        outdated_pkg_count = 0
                    if missing_ddebs:
                        missing_ddeb_count = len(missing_ddebs)
                        missing_ddebs.sort()
                        cassandra_schema.OOPS.objects.create(
                            key=oops_id.encode(),
                            column1="RetraceFailureMissingDebugSymbols",
                            value=" ".join(missing_ddebs),
                        )
                    else:
                        missing_ddebs = ""
                        missing_ddeb_count = 0
                    if crash_signature:
                        try:
                            rf_reason = (
                                cassandra_schema.BucketRetraceFailureReason.get_as_dict(
                                    key=crash_signature.encode()
                                )
                            )
                            if "missing_ddeb_count" in rf_reason:
                                least_missing_ddeb_count = int(
                                    rf_reason["missing_ddeb_count"]
                                )
                            else:
                                least_missing_ddeb_count = 9999
                            if "outdated_pkg_count" in rf_reason:
                                least_outdated_pkg_count = int(
                                    rf_reason["outdated_pkg_count"]
                                )
                            else:
                                least_outdated_pkg_count = 9999
                        except cassandra_schema.DoesNotExist:
                            least_missing_ddeb_count = 9999
                            least_outdated_pkg_count = 9999
                        if (
                            outdated_pkg_count < least_outdated_pkg_count
                            and missing_ddeb_count < least_missing_ddeb_count
                        ):
                            for k, v in {
                                "oops": oops_id,
                                "missing_ddeb_count": "%s" % missing_ddeb_count,
                                "outdated_pkg_count": "%s" % outdated_pkg_count,
                                "Reason": failure_reason,
                                "MissingDebugSymbols": "%s" % " ".join(missing_ddebs),
                                "OutdatedPackages": "%s" % " ".join(outdated_pkgs),
                            }.items():
                                cassandra_schema.BucketRetraceFailureReason.objects.create(
                                    key=crash_signature.encode(), column1=k, value=v
                                )
                        metrics.meter("retrace.failure.outdated_packages")
                        metrics.meter("retrace.failure.%s.outdated_packages" % release)
                        metrics.meter(
                            "retrace.failure.%s.outdated_packages" % architecture
                        )
                        metrics.meter(
                            "retrace.failure.%s.%s.outdated_packages"
                            % (release, architecture)
                        )
                    else:
                        pass
                else:
                    failure_reason += "."
                    cassandra_schema.OOPS.objects.create(
                        key=oops_id.encode(),
                        column1="RetraceFailureReason",
                        value=failure_reason,
                    )
                    if crash_signature:
                        for k, v in {"oops": oops_id, "Reason": failure_reason}.items():
                            cassandra_schema.BucketRetraceFailureReason.objects.create(
                                key=crash_signature.encode(), column1=k, value=v
                            )
                args = (release, day_key, retracing_time, "failed")
                self.update_retrace_stats(*args)
                metrics.meter("retrace.failed")
                metrics.meter("retrace.failed.%s" % release)
                metrics.meter("retrace.failed.%s" % architecture)
                metrics.meter("retrace.failed.%s.%s" % (release, architecture))

            # We want really quick lookups of whether we have a stacktrace for
            # this signature, so that we can quickly tell the client whether we
            # need a core dump from it.
            if stacktrace_addr_sig and crash_signature:
                cassandra_schema.Indexes.objects.create(
                    key=b"crash_signature_for_stacktrace_address_signature",
                    column1=stacktrace_addr_sig,
                    value=crash_signature.encode(),
                )
            # Use the unretraced report's SAS for the index as these were
            # created with that version of the report
            if original_sas:
                cassandra_schema.Indexes.objects.filter(
                    key=b"retracing", column1=original_sas
                ).delete()
                # This will contain the OOPS ID we're currently processing as
                # well.
                ids = list(
                    cassandra_schema.AwaitingRetrace.objects.filter(
                        key=original_sas
                    ).values_list("column1", flat=True)
                )
                oops_ids = ids
            else:
                # The initial report didn't have a SAS so don't check
                # awaiting_retrace
                ids = []

            if len(ids) == 0:
                # Handle eventual consistency. If the writes to AwaitingRetrace
                # haven't hit this node yet, that's okay. We'll clean up
                # unprocessed OOPS IDs from that CF at regular intervals later,
                # so just process this OOPS ID now.
                oops_ids = [oops_id]
                metrics.meter("missing.cannot_find_oopses_awaiting_retrace")

            if original_sas:
                try:
                    cassandra_schema.AwaitingRetrace.objects.filter(
                        key=original_sas, column1__in=oops_ids
                    ).delete()
                except cassandra_schema.DoesNotExist:
                    # An oops may not exist in awaiting_retrace if the initial
                    # report didn't have a SAS
                    pass

            if crash_signature:
                self.bucket(oops_ids, crash_signature)
                if self.rebucket(crash_signature):
                    log("Recounting %s" % crash_signature)
                    self.recount(crash_signature, msg.channel)
        finally:
            rm_eff("%s" % report_path)
            rm_eff("%s.new" % report_path)
            rm_eff(core_file)

        log("Done processing %s" % path)
        self.processed(msg)
        self._processing_callback = False
        # If stop now has been set then we should stop working.
        if self._stop_now:
            if self.connection:
                self.connection.close()
            if self.channel:
                self.channel.close()
            sys.exit()

    def processed(self, msg):
        parts = msg.body.decode().split(":", 1)
        oops_id = None
        oops_id, provider = parts
        removed = self.remove(*parts)
        if removed:
            # We've processed this. Delete it off the MQ.
            msg.channel.basic_ack(msg.delivery_tag)
            self.update_time_to_retrace(msg)
            return True
        # 2016-05-18 This was added due to intermittent issues removing core
        # files from swift. Requeue the oops_id and on the second pass we will
        # try to remove the core again or just retrace it.
        else:
            log("Requeued an OOPS (%s) whose core file was not removed." % oops_id)
            self.requeue(msg, oops_id)
        return False

    def requeue(self, msg, oops_id):
        # RabbitMQ versions from 2.7.0 push basic_reject'ed messages
        # back onto the front of the queue:
        # http://www.rabbitmq.com/semantics.html
        # Build a new message from the old one, publish the new and bin
        # the old.
        ts = msg.properties.get("timestamp")
        # If we are still unable to find the OOPS after 8 days then
        # just process it as a failure.
        today = datetime.datetime.now(datetime.UTC)
        target_date = today - datetime.timedelta(days=8)
        # if we don't know how old it is it must be ancient
        if not ts:
            log("Marked OOPS (%s) without timestamp as failed" % oops_id)
            # failed_to_process calls processed which removes the core
            self.failed_to_process(msg, oops_id, True)
            return
        if ts < target_date.timestamp():
            log("Marked old OOPS (%s) as failed" % oops_id)
            # failed_to_process calls processed which removes the core
            self.failed_to_process(msg, oops_id, True)
            return

        key = msg.delivery_info["routing_key"]

        body = amqp.Message(msg.body, timestamp=ts)
        body.properties["delivery_mode"] = 2
        msg.channel.basic_publish(body, exchange="", routing_key=key)
        msg.channel.basic_reject(msg.delivery_tag, False)

    def update_time_to_retrace(self, msg):
        """Record how long it took to retrace this crash, from the time we got
        a core file to the point that we got a either a successful or failed
        retrace out of it.
        """
        timestamp = msg.properties.get("timestamp")
        if not timestamp:
            return

        time_taken = int(datetime.datetime.now(datetime.UTC).timestamp()) - timestamp
        # This needs to be at a global level since it's dealing with the time
        # items have been sitting on a queue shared by all retracers.
        m = get_metrics("retracer.all")
        m.timing("timings.submission_to_retrace", time_taken)

    def rebucket(self, crash_signature):
        """Rebucket any failed retraces into the bucket just created for the
        given correct crash signature."""

        ids = []
        failed_key = "failed:" + crash_signature
        ids = [
            str(id).encode()
            for id in cassandra_schema.Bucket.objects.filter(
                key=failed_key
            ).values_list("column1", flat=True)
        ]

        if not ids:
            return False

        self.bucket(ids, crash_signature)

        # We don't have to remove the 'failed:' signature from
        # crash_signature_for_stacktrace_address_signature as we'll simply
        # overwrite it with the correct crash signature.
        return True

    def recount(self, crash_signature, channel):
        """Put on another queue to correct all the day counts."""

        channel.queue_declare(queue="recount", durable=True, auto_delete=False)
        body = amqp.Message(crash_signature)
        body.properties["delivery_mode"] = 2
        channel.basic_publish(body, exchange="", routing_key="recount")

    def bucket(self, ids, crash_signature):
        """Insert the provided set of OOPS ids into the bucket with the given
        crash signature."""

        for oops_id in ids:
            try:
                o = cassandra_schema.OOPS.get_as_dict(key=oops_id.encode())
            except cassandra_schema.DoesNotExist:
                log("Could not find %s for %s." % (oops_id, crash_signature))
                o = {}
            utils.bucket(self.oops_config, oops_id, crash_signature, o)
            metrics.meter("success.binary_bucketed")
            if not crash_signature.startswith("failed:") and o:
                self.cleanup_oops(oops_id)

    def cleanup_oops(self, oops_id):
        """Remove no longer needed columns from the OOPS column family for a
        specific OOPS id."""
        unneeded_columns = ["Disassembly", "ProcStatus", "Registers", "StacktraceTop"]
        cassandra_schema.OOPS.objects.filter(
            key=oops_id.encode(), column1__in=unneeded_columns
        ).delete()


def parse_options():
    parser = argparse.ArgumentParser(description="Process core dumps.")
    parser.add_argument(
        "--config-dir", help="Packaging system config base directory.", required=True
    )
    parser.add_argument(
        "-a",
        "--architecture",
        help="architecture to process (e. g. i386 or armhf)",
        required=True,
    )
    parser.add_argument(
        "--sandbox-dir",
        help="Directory for state information. Subdirectories "
        "will be created for each release for which crashes "
        "have been seen, with subdirectories under those for "
        "each instance of this program. Future runs will "
        "assume that any already downloaded package is also "
        "extracted to this sandbox.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print extra information during each retrace.",
    )
    parser.add_argument(
        "--failed", action="store_true", help="Only process previously failed retraces."
    )
    parser.add_argument(
        "--nocache-debs", action="store_true", help="Do not cache downloaded debs."
    )
    parser.add_argument(
        "--nouse-sandbox", action="store_true", help="Do not use the sandbox directory."
    )
    parser.add_argument(
        "--cleanup-sandbox",
        action="store_true",
        default=False,
        help="wipe the sandbox directory after a retrace.",
    )
    parser.add_argument(
        "--cleanup-debs",
        action="store_true",
        default=False,
        help="wipe the deb cache directory after a retrace.",
    )
    parser.add_argument(
        "--core-storage",
        help="Directory in which to store cores for manual " "investigation.",
    )
    parser.add_argument("-o", "--output", help="Log messages to a file.")
    parser.add_argument(
        "--no-stacktrace-source",
        action="store_false",
        dest="stacktrace_source",
        help="Do not have apport create a StacktraceSource.",
    )
    parser.add_argument(
        "--retrieve-core",
        help=(
            "Debug processing a single uuid:provider_id."
            "This does not touch Cassandra or the queue."
        ),
    )
    return parser.parse_args()


def main():
    global log_output
    global root_handler
    # should move to a configuration option
    global failure_storage

    options = parse_options()
    if options.output:
        path = "%s" % (options.output)
        sys.stdout.close()
        sys.stdout = open(path, "a")
        sys.stderr.close()
        sys.stderr = sys.stdout

    failure_storage = ""
    if options.core_storage:
        if os.path.exists(options.core_storage):
            failure_storage = options.core_storage

    logging.basicConfig(format=LOGGING_FORMAT, level=logging.INFO)

    try:
        msg = "Running"
        if "revno" in daisy_version_info:
            revno = daisy_version_info["revno"]
            msg += " daisy revision number: %s" % revno
            record_revno()
        if "revno" in apport_version_info:
            revno = apport_version_info["revno"]
            msg += " apport_revision number: %s" % revno
        if options.sandbox_dir:
            msg += " with sandbox_dir %s" % options.sandbox_dir
        if options.nocache_debs:
            msg += " and not caching debs"
        log(msg)

        retracer = Retracer(
            options.config_dir,
            options.sandbox_dir,
            options.architecture,
            options.verbose,
            not options.nocache_debs,
            not options.nouse_sandbox,
            options.cleanup_sandbox,
            options.cleanup_debs,
            options.stacktrace_source,
            failed=options.failed,
        )
        if options.retrieve_core:
            parts = options.one_off.split(":", 1)
            path, oops_id = retracer.write_bucket_to_disk(parts[0], parts[1])
            log("Wrote %s to %s. Exiting." % (path, oops_id))
        else:
            retracer.listen()
    except:
        # log if you want
        raise


if __name__ == "__main__":
    main()
