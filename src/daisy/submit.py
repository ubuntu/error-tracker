#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright © 2011-2013 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
#         Brian Murray <brian.murray@canonical.com>
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
import os
import socket
import time
import uuid
from binascii import hexlify, unhexlify

import bson
from apport import Report
from cassandra import WriteTimeout
from cassandra.query import SimpleStatement

from daisy import config, utils
from daisy.metrics import get_metrics
from oopsrepository import config as oopsconfig
from oopsrepository import oopses

os.environ["OOPS_KEYSPACE"] = config.cassandra_keyspace
oops_config = oopsconfig.get_config()
oops_config["host"] = config.cassandra_hosts
oops_config["username"] = config.cassandra_username
oops_config["password"] = config.cassandra_password

metrics = get_metrics("daisy.%s" % socket.gethostname())
logger = logging.getLogger("gunicorn.error")

counters_update = None
proposed_counters_update = None


def update_counters(_session, release, src_package, date, src_version=None):
    cql_release = release.replace("'", "''")
    cql_src_package = src_package.encode("ascii", errors="backslashreplace")
    if src_version:
        key = "%s:%s:%s" % (cql_release, cql_src_package, src_version)
    else:
        key = "%s:%s" % (cql_release, cql_src_package)
    _session.execute(counters_update, [key, date])


def update_proposed_counters(_session, release, src_package, date, src_version=None):
    cql_release = release.replace("'", "''")
    if src_version:
        key = "%s:%s:%s" % (cql_release, src_package, src_version)
    else:
        key = "%s:%s" % (cql_release, src_package)
    _session.execute(proposed_counters_update, [key, date])


def create_minimal_report_from_bson(data):
    report = Report()
    for key in data:
        # we don't need to add every key to the apport report to be able to
        # call crash_signature_addresses() or crash_signature()
        if key not in (
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
            continue
        try:
            report[key.encode("UTF-8")] = data[key].encode("UTF-8")
        except ValueError:
            # apport raises an ValueError if a key is invalid, given that
            # the crash has already been written to the OOPS CF, skip the key
            # and continue bucketing
            metrics.meter("invalid.invalid_key")
            msg = "Invalid key (%s) in report" % (key)
            logger.info(msg)
            continue
    return report


def try_to_repair_sas(data):
    """Try to repair the StacktraceAddressSignature, if this is a binary
    crash."""

    if all(x in data for x in ("Stacktrace", "Signal", "ProcMaps")):
        if "StacktraceAddressSignature" not in data:
            metrics.meter("repair.tried_sas")
            report = create_minimal_report_from_bson(data)
            sas = report.crash_signature_addresses()
            if sas:
                data["StacktraceAddressSignature"] = sas
                metrics.meter("repair.succeeded_sas")
            else:
                metrics.meter("repair.failed_sas")


def submit(_session, environ, system_token):
    # N.B. prepared statements do the hexlify() conversion on their own
    global counters_update
    if not counters_update:
        counters_update = _session.prepare(
            'UPDATE "Counters" SET value = value +1 WHERE key = ? and column1 = ?'
        )
    global proposed_counters_update
    if not proposed_counters_update:
        proposed_counters_update = _session.prepare(
            'UPDATE "CountersForProposed" SET value = value +1 WHERE key = ? and column1 = ?'
        )
    try:
        data = environ["wsgi.input"].read()
    except IOError as e:
        if e.message == "request data read error":
            # The client disconnected while sending the report.
            metrics.meter("invalid.connection_dropped")
            return (False, "Connection dropped.")
        else:
            raise
    try:
        if not bson.is_valid(data):
            metrics.meter("invalid.invalid_bson")
            return (False, "Invalid BSON.")
        data = bson.BSON(data).decode()
    except bson.errors.InvalidBSON:
        metrics.meter("invalid.invalid_bson")
        return (False, "Invalid BSON.")
    except bson.errors.InvalidDocument:
        metrics.meter("invalid.invalid_bson_doc")
        return (False, "Invalid BSON Document.")
    except MemoryError:
        metrics.meter("invalid.memory_error_bson")
        return (False, "Invalid BSON.")

    # Keep a reference to the decoded report data. If we crash, we'll
    # potentially attach it to the OOPS report.
    environ["wsgi.input.decoded"] = data

    oops_id = str(uuid.uuid1())

    # In theory one should be able to use map_environ with make_app in
    # oops_wsgi to write arbitary data to the OOPS report but I couldn't get
    # that to work so cheat and uses HTTP_ which always gets written.
    environ["HTTP_Z_CRASH_ID"] = oops_id

    day_key = time.strftime("%Y%m%d", time.gmtime())

    if "KernelCrash" in data or "VmCore" in data:
        # We do not process these yet, but we keep track of how many reports
        # we're receiving to determine when it's worth solving.
        metrics.meter("unsupported.kernel_crash")
        return (False, "Kernel crashes are not handled yet.")

    if len(data) == 0:
        metrics.meter("invalid.empty_report")
        return (False, "Empty report.")

    # Write the SHA512 hash of the system UUID in with the report.
    if system_token:
        data["SystemIdentifier"] = system_token
    else:
        # we want to try and find out which releases are sending reports with
        # a missing SystemIdentifier
        try:
            whoopsie_version = environ["HTTP_X_WHOOPSIE_VERSION"]
            metrics.meter(
                "missing.missing_system_token_%s" % whoopsie_version.replace(".", "_")
            )
        except KeyError:
            pass
        metrics.meter("missing.missing_system_token")

    release = data.get("DistroRelease", "")
    if release in utils.EOL_RELEASES:
        metrics.meter("unsupported.eol_%s" % utils.EOL_RELEASES[release])
        return (False, "%s is End of Life" % str(release))
    arch = data.get("Architecture", "")
    # We cannot retrace without an architecture to do it on
    if not arch:
        metrics.meter("missing.missing_arch")
    if arch == "armel":
        metrics.meter("unsupported.armel")
        return (False, "armel architecture is obsoleted.")
    # Check to see if the crash has already been reported
    date = data.get("Date", "")
    exec_path = data.get("ExecutablePath", "")
    proc_status = data.get("ProcStatus", "")
    if date and exec_path and proc_status and system_token:
        try:
            cql_system_token = "0x" + hexlify(system_token)
            results = _session.execute(
                SimpleStatement(
                    'SELECT column1 FROM "%s" WHERE key = %s LIMIT 1'
                    % ("SystemOOPSHashes", cql_system_token)
                )
            )
            reported_crash_ids = (row[0] for row in results)
            crash_id = "%s:%s:%s" % (date, exec_path, proc_status)
            if isinstance(crash_id, str):
                crash_id = crash_id.encode("utf-8")
            crash_id = hashlib.md5(crash_id).hexdigest()
            if crash_id in reported_crash_ids:
                return (False, "Crash already reported.")
            try:
                whoopsie_version = environ["HTTP_X_WHOOPSIE_VERSION"]
                metrics.meter(
                    "invalid.duplicate_report.whoopise_%s"
                    % whoopsie_version.replace(".", "_")
                )
            except KeyError:
                pass
            metrics.meter("invalid.duplicate_report")
        except IndexError:
            pass
    package = data.get("Package", "")
    # If the crash report does not have a package then it will not be
    # retraceable and we should not write it to the OOPS table. It seems that
    # apport is flagging crashes for submission even though data collection is
    # incomplete.
    if not package:
        logger.info("Crash report did not contain a package.")
        return (False, "Incomplete crash report.")
    pkg_arch = utils.get_package_architecture(data)
    # according to debian policy neither the package or version should have
    # utf8 in it but either some archives do not know that or something is
    # wonky with apport
    src_package = data.get("SourcePackage", "")
    src_package = src_package.encode("ascii", errors="replace")
    environ["HTTP_Z_SRC_PKG"] = src_package
    problem_type = data.get("ProblemType", "")
    environ["HTTP_Z_PROBLEMTYPE"] = problem_type
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
            return (False, "Incomplete suspend resume data found in report.")
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
        return (True, "Crash report successfully submitted.")

    package, version = utils.split_package_and_version(package)
    environ["HTTP_Z_PKG"] = package
    # src_version is None and is never used, nor should it be.
    src_package, src_version = utils.split_package_and_version(src_package)
    fields = utils.get_fields_for_bucket_counters(
        problem_type, release, package, version, pkg_arch
    )

    # generic counter for crashes about a source package which is used by the
    # phased-updater and only includes official Ubuntu packages and not those
    # crahses from systems under auto testing.
    if not third_party and not automated_testing and problem_type == "Crash":
        update_counters(
            _session, release=release, src_package=src_package, date=day_key
        )
        if version == "":
            metrics.meter("missing.missing_package_version")
        else:
            update_counters(
                _session,
                release=release,
                src_package=src_package,
                src_version=version,
                date=day_key,
            )

    try_to_repair_sas(data)
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
        # generic counter for crashes about a source package which is used by
        # the phased-updater and only includes official Ubuntu packages and
        # not those from systems under auto testing.
        if not third_party and not automated_testing and problem_type == "Crash":
            update_proposed_counters(
                _session, release=release, src_package=src_package, date=day_key
            )
            if version != "":
                update_proposed_counters(
                    _session,
                    release=release,
                    src_package=src_package,
                    src_version=version,
                    date=day_key,
                )

    # A device is manually blocklisted if it has repeatedly failed to have an
    # crash inserted into the OOPS table.
    if utils.blocklisted_device(system_token):
        # If the device stops appearing in the log file then the offending
        # crash file may have been removed and it could be unblocklisted.
        logger.info(
            "Blocklisted device %s disallowed from sending a crash." % system_token
        )
        return (False, "Device blocked from sending crash reports.")

    try:
        if problem_type == "Snap":
            expire = True
        else:
            expire = False
        oopses.insert_dict(
            _session,
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
        logger.info(
            "%s: The crash has a ProblemType of: %s" % (system_token, problem_type)
        )
        if "Traceback" in data:
            logger.info("%s: The crash has a python traceback." % system_token)
        raise
    msg = "(%s) inserted into OOPS CF" % (oops_id)
    logger.info(msg)
    metrics.meter("success.oopses")
    if arch:
        metrics.meter("success.oopses.%s" % arch)

    success, output = bucket(_session, oops_config, oops_id, data, day_key)
    return (success, output)


def bucket(_session, oops_config, oops_id, data, day_key):
    """Bucket oops_id.
    If the report was malformed, return (False, failure_msg)
    If a core file is to be requested, return (True, 'UUID CORE')
    If no further action is needed, return (True, 'UUID OOPSID')
    """
    indexes_select = None
    if not indexes_select:
        indexes_select = _session.prepare(
            'SELECT value FROM "Indexes" WHERE key = ? and column1 = ? LIMIT 1'
        )
    stacktrace_select = None
    if not stacktrace_select:
        stacktrace_select = _session.prepare(
            'SELECT value FROM "Stacktrace" WHERE key = ? and column1 = ? LIMIT 1'
        )

    release = data.get("DistroRelease", "")

    # Recoverable Problem, Package Install Failure, Suspend Resume
    crash_signature = data.get("DuplicateSignature", "")
    if crash_signature:
        crash_signature = utils.format_crash_signature(crash_signature)
        utils.bucket(_session, oops_id, crash_signature, data)
        metrics.meter("success.duplicate_signature")
        return (True, "%s OOPSID" % oops_id)

    # Python
    if "Traceback" in data:
        report = create_minimal_report_from_bson(data)
        crash_signature = report.crash_signature()
        if crash_signature:
            hex_oopsid = "0x" + hexlify(oops_id)
            cql_crash_sig = crash_signature.replace("'", "''")
            _session.execute(
                SimpleStatement(
                    "INSERT INTO \"%s\" (key, column1, value) VALUES (%s, 'DuplicateSignature', '%s')"
                    % ("OOPS", hex_oopsid, cql_crash_sig)
                )
            )
            formatted_crash_sig = utils.format_crash_signature(crash_signature)
            cql_formatted_crash_sig = formatted_crash_sig.replace("'", "''")
            utils.bucket(_session, oops_id, cql_formatted_crash_sig, data)
            metrics.meter("success.python_bucketed")
            return (True, "%s OOPSID" % oops_id)

    # Crashing binary
    if "StacktraceTop" in data and "Signal" in data:
        output = ""
        # we check for addr_sig before bucketing and inserting into oopses
        addr_sig = data.get("StacktraceAddressSignature", None)
        crash_sig = ""
        if addr_sig:
            cql_addr_sig = addr_sig.replace("'", "''")
            cql_addr_sig = cql_addr_sig.encode("ascii", errors="backslashreplace")
            # TODO: create a method to set retry = True for specific SASes
            # LP: #1505818
            try:
                key = "crash_signature_for_stacktrace_address_signature"
                results = _session.execute(indexes_select, [key, cql_addr_sig])
                cql_crash_sig = [row[0] for row in results][0]
                # remove the 0x in the beginning
                if cql_crash_sig.startswith("0x"):
                    crash_sig = unhexlify(cql_crash_sig[2:])
                else:
                    crash_sig = cql_crash_sig
            except IndexError:
                pass
        else:
            cql_addr_sig = addr_sig
        failed_to_retrace = False
        if crash_sig.startswith("failed:"):
            failed_to_retrace = True
        # for some crashes apport isn't creating a Stacktrace in the
        # successfully retraced report, we need to retry these even though
        # there is a crash_sig
        stacktrace = False
        if cql_addr_sig:
            try:
                stacktraces = _session.execute(
                    stacktrace_select, [cql_addr_sig, "Stacktrace"]
                )
                stacktrace = [stacktrace[0] for stacktrace in stacktraces][0]
                threadstacktraces = _session.execute(
                    stacktrace_select, [cql_addr_sig, "ThreadStacktrace"]
                )
                tstacktrace = [tstacktrace[0] for tstacktrace in threadstacktraces][0]
                if stacktrace and tstacktrace:
                    stacktrace = True
            except IndexError:
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
            if arch == "amd64" and release in ("Ubuntu 24.04", "Ubuntu 24.10"):
                retry = True
        if crash_sig and not retry:
            # The crash is a duplicate so we don't need this data.
            # Stacktrace, and ThreadStacktrace were already not accepted
            if "ProcMaps" in data:
                oops_delete = _session.prepare(
                    'DELETE FROM "OOPS" WHERE key = ? AND column1 = ?'
                )
                unneeded_columns = (
                    "Disassembly",
                    "ProcMaps",
                    "ProcStatus",
                    "Registers",
                    "StacktraceTop",
                )
                for unneeded_column in unneeded_columns:
                    _session.execute(oops_delete, [oops_id, unneeded_column])
            # We have already retraced for this address signature, so this
            # crash can be immediately bucketed.
            utils.bucket(_session, oops_id, crash_sig, data)
            metrics.meter("success.ready_binary_bucketed")
            if arch:
                metrics.meter("success.ready_binary_bucketed.%s" % arch)
        else:
            # apport requires the following fields to be able to retrace a
            # crash so do not ask for a CORE file if they don't exist
            if not release:
                return (True, "%s OOPSID" % oops_id)
            # do not ask for a core file for crashes using the old version of
            # libc6 since they won't be retraceable. LP: #1760207
            if release == "Ubuntu 18.04":
                deps = data.get("Dependencies", "")
                libc = [d for d in deps.split("\n") if d.startswith("libc6 2.26-0")]
                try:
                    if libc[0].startswith("libc6 2.26-0"):
                        return (True, "%s OOPSID" % oops_id)
                except (KeyError, IndexError):
                    pass
            package = data.get("Package", "")
            if not package:
                return (True, "%s OOPSID" % oops_id)
            exec_path = data.get("ExecutablePath", "")
            if not exec_path:
                return (True, "%s OOPSID" % oops_id)
            # Are we already waiting for this stacktrace address signature to
            # be retraced?
            waiting = False
            if cql_addr_sig:
                try:
                    key = "retracing"
                    results = _session.execute(indexes_select, [key, cql_addr_sig])
                    waiting = True
                except IndexError:
                    pass

            if not waiting and utils.retraceable_release(release):
                # there will not be a debug symbol version of the package so
                # don't ask for a CORE
                if not utils.retraceable_package(package):
                    metrics.meter("missing.retraceable_origin")
                    return (True, "%s OOPSID" % oops_id)
                # Don't ask for cores from things like google-chrome-stable
                # which will appear as "not installed" if installed from a
                # .deb
                if "(not installed)" in package:
                    metrics.meter("missing.package_version")
                    return (True, "%s OOPSID" % oops_id)
                # retry SASes that failed to retrace as new dbgsym packages
                # may be available
                if crash_sig and retry:
                    metrics.meter("success.retry_failure")
                    msg = "will retry retrace of: %s" % (oops_id)
                    logger.info(msg)
                elif crash_sig and not retry:
                    # Do not ask for a core for crashes we don't want to retry
                    metrics.meter("success.not_retry_failure")
                    return (True, "%s OOPSID" % oops_id)
                elif not addr_sig and not retry:
                    # Do not ask for a core for crashes without a SAS as they
                    # are likely corrupt cores.
                    metrics.meter("success.not_retry_no_sas")
                    return (True, "%s OOPSID" % oops_id)
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
                _session.execute(
                    SimpleStatement(
                        "INSERT INTO \"%s\" (key, column1, value) VALUES ('%s', '%s', '%s')"
                        % ("AwaitingRetrace", cql_addr_sig, oops_id, "")
                    )
                )
            metrics.meter("success.awaiting_binary_bucket")
        if not output:
            output = "%s OOPSID" % oops_id
        return (True, output)

    # Could not bucket
    hex_day_key = "0x" + hexlify(day_key)
    _session.execute(
        SimpleStatement(
            'INSERT INTO "%s" (key, column1, value) VALUES (%s, %s, %s)'
            % ("CouldNotBucket", hex_day_key, uuid.UUID(oops_id), "0x")
        )
    )
    return (True, "%s OOPSID" % oops_id)
