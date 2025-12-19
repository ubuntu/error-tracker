#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright © 2011-2025 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
#         Brian Murray <brian.murray@canonical.com>
#         Florent 'Skia' Jacquet <florent.jacquet@canonical.com>
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

import hashlib
import logging
import socket
import time
import uuid

import bson
from apport import Report
from cassandra import WriteTimeout
from cassandra.cqlengine.query import DoesNotExist

from daisy.metrics import get_metrics
from errortracker import cassandra_schema, oopses, utils

metrics = get_metrics("daisy.%s" % socket.gethostname())
logger = logging.getLogger("daisy")


def create_minimal_report_from_bson(data):
    report = Report()
    for key in data:
        # we don't need to add every key to the apport report to be able to
        # call crash_signature_addresses() or crash_signature()
        if key in (
            "ProcMaps",
            "Stacktrace",
            "Signal",
            "ExecutablePath",
            "ProblemType",
            "AssertionMessage",
            "StacktraceTop",
            "Traceback",
            "KernelOops",
            "Failure",
            "_PythonExceptionQualifier",
            "MachineType",
            "dmi.bios.version",
            "OopsText",
        ):
            try:
                report[key] = data[key]
            except ValueError:
                # apport raises an ValueError if a key is invalid, given that
                # the crash has already been written to the OOPS CF, skip the key
                # and continue bucketing
                metrics.meter("invalid.invalid_key")
                logger.info("Invalid key (%s) in report", key)
                continue
    return report


def submit(request, system_token):
    logger.info("Submit handler")
    logger.info(f"request: {request}")
    data = request.data
    try:
        if not bson.is_valid(data):
            metrics.meter("invalid.invalid_bson")
            return "Invalid BSON.", 400
        data = bson.BSON(data).decode()
    except bson.errors.InvalidBSON:
        metrics.meter("invalid.invalid_bson")
        return "Invalid BSON.", 400
    except bson.errors.InvalidDocument:
        metrics.meter("invalid.invalid_bson_doc")
        return "Invalid BSON Document.", 400
    except MemoryError:
        metrics.meter("invalid.memory_error_bson")
        return "Invalid BSON.", 400

    oops_id = str(uuid.uuid1())

    day_key = time.strftime("%Y%m%d", time.gmtime())

    if "KernelCrash" in data or "VmCore" in data:
        # We do not process these yet, but we keep track of how many reports
        # we're receiving to determine when it's worth solving.
        metrics.meter("unsupported.kernel_crash")
        return "Kernel crashes are not handled yet.", 400

    if len(data) == 0:
        metrics.meter("invalid.empty_report")
        return "Empty report.", 400

    # Write the SHA512 hash of the system UUID in with the report.
    if system_token:
        data["SystemIdentifier"] = system_token
    else:
        # we want to try and find out which releases are sending reports with
        # a missing SystemIdentifier
        try:
            whoopsie_version = request.headers["X-Whoopsie-Version"]
            metrics.meter("missing.missing_system_token_%s" % whoopsie_version.replace(".", "_"))
        except KeyError:
            pass
        metrics.meter("missing.missing_system_token")

    release = data.get("DistroRelease", "")
    if release in utils.EOL_RELEASES:
        metrics.meter("unsupported.eol_%s" % utils.EOL_RELEASES[release])
        return f"{release} is End of Life", 400
    arch = data.get("Architecture", "")
    # We cannot retrace without an architecture to do it on
    if not arch:
        metrics.meter("missing.missing_arch")
    if arch == "armel":
        metrics.meter("unsupported.armel")
        return "armel architecture is obsoleted.", 400
    # Check to see if the crash has already been reported
    date = data.get("Date", "")
    exec_path = data.get("ExecutablePath", "")
    proc_status = data.get("ProcStatus", "")
    if date and exec_path and proc_status and system_token:
        try:
            results = list(
                cassandra_schema.SystemOOPSHashes.objects.filter(key=system_token.encode())
            )
            reported_crash_ids = (row.column1 for row in results)
            crash_id = f"{date}:{exec_path}:{proc_status}"
            crash_id = hashlib.md5(crash_id.encode()).hexdigest()
            if crash_id in reported_crash_ids:
                return "Crash already reported.", 409
            try:
                whoopsie_version = request.headers["X-Whoopsie-Version"]
                metrics.meter(
                    "invalid.duplicate_report.whoopsie_%s" % whoopsie_version.replace(".", "_")
                )
            except KeyError:
                pass
            metrics.meter("invalid.duplicate_report")
        except IndexError:
            pass
    # according to debian policy neither the package or version should have
    # utf8 in it but either some archives do not know that or something is
    # wonky with apport
    package = data.get("Package", "").encode("ascii", errors="replace").decode()
    src_package = data.get("SourcePackage", "").encode("ascii", errors="replace").decode()
    # If the crash report does not have a package then it will not be
    # retraceable and we should not write it to the OOPS table. It seems that
    # apport is flagging crashes for submission even though data collection is
    # incomplete.
    if not package:
        logger.info("Crash report did not contain a package.")
        return "Incomplete crash report.", 400
    pkg_arch = utils.get_package_architecture(data)
    problem_type = data.get("ProblemType", "")
    apport_version = data.get("ApportVersion", "")
    third_party = False
    if not utils.retraceable_package(package):
        third_party = True
    automated_testing = False
    if system_token.startswith("deadbeef"):
        automated_testing = True

    if not release:
        metrics.meter("missing.missing_release")
    if not package:
        metrics.meter("missing.missing_package")
    if not problem_type:
        metrics.meter("missing.missing_problem_type")
    if not exec_path:
        metrics.meter("missing.missing_executable_path")
    if exec_path.endswith("apportcheckresume"):
        # LP: #1316841 bad duplicate signatures
        if release == "Ubuntu 14.04" and apport_version == "2.14.1-0ubuntu3.1":
            metrics.meter("missing.missing_suspend_resume_data")
            return "Incomplete suspend resume data found in report.", 400
        failure = data.get("Failure", "")
        if failure == "suspend/resume" and "ProcMaps" in data:
            # this is not useful as it is from the resuming system
            data.pop("ProcMaps")
    else:
        metrics.meter("success.problem_type.%s" % problem_type)

    # 2023-03-15 Tell the client that we accepted the crash report even though
    # we aren't really writing it to the database. This is a stop gap measure
    # while database size issues are addressed.
    if problem_type == "Snap":
        return "Crash report successfully submitted.", 200

    package, version = utils.split_package_and_version(package)
    # src_version is None and is never used, nor should it be.
    src_package, src_version = utils.split_package_and_version(src_package)
    fields = utils.get_fields_for_bucket_counters(
        problem_type, release, package, version, pkg_arch
    )

    # ProcMaps is useful for creating a crash sig, not after that
    if "Traceback" in data and "ProcMaps" in data:
        data.pop("ProcMaps")
    # we only want this data after retracing with debug symbols
    if "Stacktrace" in data:
        data.pop("Stacktrace")
    if "ThreadStacktrace" in data:
        data.pop("ThreadStacktrace")
    if "StacktraceTop" in data and "Signal" in data:
        addr_sig = data.get("StacktraceAddressSignature", None)
        if not addr_sig and arch:
            metrics.meter("missing.missing_sas_%s" % arch)
        metrics.meter("missing.missing_sas")

    # We don't know how many lines of JournalErrors will be useful so limit it
    # on the receiving end not on the sending one i.e. from whoopsie.
    jerrors = data.get("JournalErrors", "")
    if jerrors:
        jerrors = [line for line in jerrors.split("\n")][-50:]
        data["JournalErrors"] = "\n".join(jerrors)

    tags = data.get("Tags", "")

    package_from_proposed = False
    if "package-from-proposed" in tags:
        package_from_proposed = True

    # A device is manually blocklisted if it has repeatedly failed to have an
    # crash inserted into the OOPS table.
    if utils.blocklisted_device(system_token):
        # If the device stops appearing in the log file then the offending
        # crash file may have been removed and it could be unblocklisted.
        logger.info("Blocklisted device %s disallowed from sending a crash." % system_token)
        return "Device blocked from sending crash reports.", 401

    try:
        if problem_type == "Snap":
            expire = True
        else:
            expire = False
        oopses.insert_dict(
            oops_id,
            data,
            system_token,
            fields,
            proposed_pkg=package_from_proposed,
            ttl=expire,
        )
    except WriteTimeout:
        msg = "%s: WriteTimeout with %s keys." % (system_token, len(list(data.keys())))
        logger.info(msg)
        logger.info("%s: The keys are %s" % (system_token, list(data.keys())))
        logger.info("%s: The crash has a ProblemType of: %s" % (system_token, problem_type))
        if "Traceback" in data:
            logger.info("%s: The crash has a python traceback." % system_token)
        raise
    msg = "(%s) inserted into OOPS CF" % (oops_id)
    logger.info(msg)
    metrics.meter("success.oopses")
    if arch:
        metrics.meter("success.oopses.%s" % arch)

    output, code = bucket(oops_id, data, day_key)
    return (output, code)


def bucket(oops_id, data, day_key):
    """Bucket oops_id.
    If the report was malformed, return (False, failure_msg)
    If a core file is to be requested, return (True, 'UUID CORE')
    If no further action is needed, return (True, 'UUID OOPSID')
    """
    release = data.get("DistroRelease", "")

    # Recoverable Problem, Package Install Failure, Suspend Resume
    crash_signature = data.get("DuplicateSignature", "")
    if crash_signature:
        crash_signature = utils.format_crash_signature(crash_signature)
        utils.bucket(oops_id, crash_signature, data)
        metrics.meter("success.duplicate_signature")
        return "%s OOPSID" % oops_id, 200

    # Python
    if "Traceback" in data:
        report = create_minimal_report_from_bson(data)
        crash_signature = report.crash_signature()
        if crash_signature:
            cassandra_schema.OOPS.create(
                key=oops_id.encode(), column1="DuplicateSignature", value=crash_signature
            )
            formatted_crash_sig = utils.format_crash_signature(crash_signature)
            cql_formatted_crash_sig = formatted_crash_sig.replace("'", "''")
            utils.bucket(oops_id, cql_formatted_crash_sig, data)
            metrics.meter("success.python_bucketed")
            return "%s OOPSID" % oops_id, 200

    # Crashing binary
    if "StacktraceTop" in data and "Signal" in data:
        output = ""
        # we check for addr_sig before bucketing and inserting into oopses
        addr_sig = data.get("StacktraceAddressSignature", None)
        crash_sig = ""
        if addr_sig:
            try:
                crash_sig = cassandra_schema.Indexes.get(
                    key=b"crash_signature_for_stacktrace_address_signature", column1=addr_sig
                ).value.decode()
            except DoesNotExist:
                pass
        failed_to_retrace = False
        if crash_sig.startswith("failed:"):
            failed_to_retrace = True
        # for some crashes apport isn't creating a Stacktrace in the
        # successfully retraced report, we need to retry these even though
        # there is a crash_sig
        stacktrace = False
        if addr_sig:
            try:
                stacktrace = cassandra_schema.Stacktrace.get(
                    key=addr_sig.encode(), column1="Stacktrace"
                ).value
                tstacktrace = cassandra_schema.Stacktrace.get(
                    key=addr_sig.encode(), column1="ThreadStacktrace"
                ).value
                if stacktrace and tstacktrace:
                    stacktrace = True
            except DoesNotExist:
                metrics.meter("missing.missing_retraced_stacktrace")
                pass
        retry = False
        # If the retrace was successful but we don't have a stacktrace
        # something is wrong, so try retracing it again.
        if not failed_to_retrace and not stacktrace:
            retry = True
        arch = data.get("Architecture", "")
        if failed_to_retrace:
            # retry amd64 crashes which failed to retrace for LTS and current
            # development releases, don't do it for every release b/c we have
            # a limited number of retracers
            if arch == "amd64" and release in ("Ubuntu 24.04", "Ubuntu 25.10"):
                retry = True
        if crash_sig and not retry:
            # The crash is a duplicate so we don't need this data.
            # Stacktrace, and ThreadStacktrace were already not accepted
            if "ProcMaps" in data:
                unneeded_columns = (
                    "Disassembly",
                    "ProcMaps",
                    "ProcStatus",
                    "Registers",
                    "StacktraceTop",
                )
                for unneeded_column in unneeded_columns:
                    cassandra_schema.OOPS.filter(key=oops_id.encode(), column1=unneeded_column).delete()
            # We have already retraced for this address signature, so this
            # crash can be immediately bucketed.
            utils.bucket(oops_id, crash_sig, data)
            metrics.meter("success.ready_binary_bucketed")
            if arch:
                metrics.meter("success.ready_binary_bucketed.%s" % arch)
        else:
            # apport requires the following fields to be able to retrace a
            # crash so do not ask for a CORE file if they don't exist
            if not release:
                return f"{oops_id} OOPSID", 200
            package = data.get("Package", "")
            if not package:
                return f"{oops_id} OOPSID", 200
            exec_path = data.get("ExecutablePath", "")
            if not exec_path:
                return f"{oops_id} OOPSID", 200
            # Are we already waiting for this stacktrace address signature to
            # be retraced?
            waiting = False
            if addr_sig:
                try:
                    cassandra_schema.Indexes.get(key="retracing".encode(), column1=addr_sig)
                    waiting = True
                except DoesNotExist:
                    pass

            if not waiting and utils.retraceable_release(release):
                # there will not be a debug symbol version of the package so
                # don't ask for a CORE
                if not utils.retraceable_package(package):
                    metrics.meter("missing.retraceable_origin")
                    return f"{oops_id} OOPSID", 200
                # Don't ask for cores from things like google-chrome-stable
                # which will appear as "not installed" if installed from a
                # .deb
                if "(not installed)" in package:
                    metrics.meter("missing.package_version")
                    return "%s OOPSID" % oops_id, 200
                # retry SASes that failed to retrace as new dbgsym packages
                # may be available
                if crash_sig and retry:
                    metrics.meter("success.retry_failure")
                    msg = "will retry retrace of: %s" % (oops_id)
                    logger.info(msg)
                elif crash_sig and not retry:
                    # Do not ask for a core for crashes we don't want to retry
                    metrics.meter("success.not_retry_failure")
                    return "%s OOPSID" % oops_id, 200
                elif not addr_sig and not retry:
                    # Do not ask for a core for crashes without a SAS as they
                    # are likely corrupt cores.
                    metrics.meter("success.not_retry_no_sas")
                    return "%s OOPSID" % oops_id, 200
                # We do not have a core file in the queue, so ask for one. Do
                # not assume we're going to get one, so also add this ID the
                # the AwaitingRetrace CF queue as well.

                # We don't ask derivatives for core dumps. We could technically
                # check to make sure the Packages and Dependencies fields do
                # not have '[origin:' lines; however, apport-retrace looks for
                # configuration data in a directory named by the
                # DistroRelease, so these would always fail regardless.
                output = "%s CORE" % oops_id
                msg = "(%s) asked for CORE" % (oops_id)
                logger.info(msg)
                metrics.meter("success.asked_for_core")
                if arch:
                    metrics.meter("success.asked_for_core.%s" % arch)
                if release:
                    metrics.meter("success.asked_for_core.%s" % release)
            if addr_sig:
                cassandra_schema.AwaitingRetrace.create(key=addr_sig, column1=oops_id, value="")
            metrics.meter("success.awaiting_binary_bucket")
        if not output:
            output = "%s OOPSID" % oops_id
        return output, 200

    # Could not bucket
    cassandra_schema.CouldNotBucket.create(
        key=day_key.encode(), column1=uuid.UUID(oops_id), value=b""
    )
    return "%s OOPSID" % oops_id, 200
