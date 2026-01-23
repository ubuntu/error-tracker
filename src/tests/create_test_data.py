import locale
import logging
import uuid
from datetime import datetime, timedelta

import bson
from apport import Report

from daisy.submit import submit
from errortracker import cassandra_schema as schema
from errortracker import utils


def create_test_data(datetime_now=datetime.now()):
    # disable daisy logger temporarily
    daisy_logger = logging.getLogger("daisy")
    daisy_logger_level = daisy_logger.level
    daisy_logger.setLevel(51)  # CRITICAL is 50, so let's go higher

    # Make sure the datetime will get formatted "correctly" in that cursed time format: Mon May  5 14:46:10 2025
    locale.setlocale(locale.LC_ALL, "C.UTF-8")

    def new_oops(days_ago, data, systemid="imatestsystem"):
        crash_date = datetime_now - timedelta(days=days_ago)
        oops_date = crash_date.strftime("%c")
        data.update({"Date": oops_date})
        bson_data = bson.encode(data)
        request = type(
            "Request",
            (object,),
            dict(data=bson_data, headers={"X-Whoopsie-Version": "0.2.81ubuntu~fakefortesting"}),
        )
        submit(request, systemid)

    # Get a wide screen, because here we'll want to have compact data, meaning long lines 🙃
    # fmt: off

    # increase-rate package version 1
    for i in [30, 20, 10, 5, 2]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "increase-rate 1", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/increase-rate", "StacktraceAddressSignature": "/usr/bin/increase-rate:42:/usr/bin/increase-rate+28"})

    # increase-rate package version 2
    for i in [2, 2, 1, 1, 1, 0, 0, 0, 0]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "increase-rate 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/increase-rate", "StacktraceAddressSignature": "/usr/bin/increase-rate:42:/usr/bin/increase-rate+fa0"})

    # increase-rate package version 2 in proposed, even more crashes!
    for i in [1, 0]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "increase-rate 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/increase-rate", "StacktraceAddressSignature": "/usr/bin/increase-rate:42:/usr/bin/increase-rate+fa0", "Tags": "package-from-proposed"})

    # no-crashes-today package version 1 (old version with crashes)
    for i in [30, 20, 10, 5, 2]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "no-crashes-today 1", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/no-crashes-today", "StacktraceAddressSignature": "/usr/bin/no-crashes-today:1:/usr/bin/no-crashes-today+10"})

    # no-crashes-today package version 2 (no crashes today - last crash was yesterday)
    for i in [5, 3, 1]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "no-crashes-today 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/no-crashes-today", "StacktraceAddressSignature": "/usr/bin/no-crashes-today:2:/usr/bin/no-crashes-today+20"})

    # few-crashes package version 1 (old version with crashes)
    for i in [30, 20, 10, 5, 2]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "few-crashes 1", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/few-crashes", "StacktraceAddressSignature": "/usr/bin/few-crashes:1:/usr/bin/few-crashes+10"})

    # few-crashes package version 2 (only 2 crashes today - less than threshold of 3)
    for i in [0, 0]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "few-crashes 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/few-crashes", "StacktraceAddressSignature": "/usr/bin/few-crashes:2:/usr/bin/few-crashes+20"})

    # new-package (no old version - should always be increase=True)
    for i in [0, 0, 0, 0, 0]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "new-package 1", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/new-package", "StacktraceAddressSignature": "/usr/bin/new-package:1:/usr/bin/new-package+10"})

    # low-difference package version 1 (old version with consistent crashes)
    for i in [30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "low-difference 1", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/low-difference", "StacktraceAddressSignature": "/usr/bin/low-difference:1:/usr/bin/low-difference+10"})

    # low-difference package version 2 (similar crash rate to version 1, so difference should be low)
    # Only 1 crash today which is less than the expected average
    for i in [0]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "low-difference 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/low-difference", "StacktraceAddressSignature": "/usr/bin/low-difference:2:/usr/bin/low-difference+20"})

    # all-proposed package version 1
    for i in [30, 20, 10]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "all-proposed 1", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/all-proposed", "StacktraceAddressSignature": "/usr/bin/all-proposed:1:/usr/bin/all-proposed+10"})

    # all-proposed package version 2 (all crashes today are from proposed)
    for i in [0, 0, 0, 0]:
        new_oops(i, {"DistroRelease": "Ubuntu 24.04", "Package": "all-proposed 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/all-proposed", "StacktraceAddressSignature": "/usr/bin/all-proposed:2:/usr/bin/all-proposed+20", "Tags": "package-from-proposed"})
    # fmt: on

    # a retraced and bucketed report
    report = Report()
    report["DistroRelease"] = "Ubuntu 24.04"
    report["Package"] = "already-bucketed 1.0"
    report["SourcePackage"] = "already-bucketed-src"
    report["ExecutablePath"] = "/usr/bin/already-bucketed"
    report["Signal"] = "11"
    report["StacktraceTop"] = "func1 () at already-bucketed.c:42\nmain () at already-bucketed.c:14"
    report["StacktraceAddressSignature"] = (
        "/usr/bin/already-bucketed:42:/usr/bin/already-bucketed+28"
    )
    report["Stacktrace"] = (
        "#0  0x40004000 in func1 () at ./already-bucketed.c:42\n"
        "#1  0x40005000 in main () at ./already-bucketed.c:14\n"
    )
    report["ThreadStacktrace"] = (
        ".\nThread 1 (Thread 0x42424242 (LWP 4000)):\n"
        "#0  0x40004000 in func1 () at ./already-bucketed.c:42\n"
        "#1  0x40005000 in main () at ./already-bucketed.c:14\n"
    )
    utils.bucket(str(uuid.uuid1()), report.crash_signature(), report)
    # emulate the retracer
    schema.Indexes.objects.create(
        key=b"crash_signature_for_stacktrace_address_signature",
        column1=report["StacktraceAddressSignature"],
        value=report.crash_signature().encode(),
    )
    schema.Stacktrace.objects.create(
        key=report["StacktraceAddressSignature"].encode(),
        column1="Stacktrace",
        value=report["Stacktrace"],
    )
    schema.Stacktrace.objects.create(
        key=report["StacktraceAddressSignature"].encode(),
        column1="ThreadStacktrace",
        value=report["ThreadStacktrace"],
    )

    # another similar crash
    new_oops(
        0,
        {
            "DistroRelease": "Ubuntu 26.04",
            "Architecture": "amd64",
            "Package": "already-bucketed 2.0",
            "SourcePackage": "already-bucketed-src",
            "ProblemType": "Crash",
            "ExecutablePath": "/usr/bin/already-bucketed",
            "StacktraceAddressSignature": report["StacktraceAddressSignature"],
            "StacktraceTop": report["StacktraceTop"],
            "Signal": report["Signal"],
        },
    )

    # a failed retrace report
    failed_report = Report()
    failed_report["DistroRelease"] = "Ubuntu 24.04"
    failed_report["Package"] = "failed-retrace 1.0"
    failed_report["SourcePackage"] = "failed-retrace-src"
    failed_report["ExecutablePath"] = "/usr/bin/failed-retrace"
    failed_report["Signal"] = "11"
    failed_report["StacktraceTop"] = "failed_func () at failed.c:10\nmain () at failed.c:5"
    failed_report["StacktraceAddressSignature"] = (
        "/usr/bin/failed-retrace:11:/usr/bin/failed-retrace+100"
    )
    utils.bucket(str(uuid.uuid1()), failed_report.crash_signature(), failed_report)
    # emulate a failed retrace with failure reasons
    schema.BucketRetraceFailureReason.objects.create(
        key=failed_report.crash_signature().encode(),
        column1="missing-debug-symbols",
        value="Debug symbols not available for package failed-retrace",
    )
    schema.BucketRetraceFailureReason.objects.create(
        key=failed_report.crash_signature().encode(),
        column1="retrace-error",
        value="Failed to generate stacktrace",
    )

    # a Python crash
    python_report = Report()
    python_report["DistroRelease"] = "Ubuntu 24.04"
    python_report["Package"] = "python3-traceback 1.0"
    python_report["SourcePackage"] = "python-traceback"
    python_report["ExecutablePath"] = "/usr/bin/pytraceback"
    python_report["Traceback"] = (
        "Traceback (most recent call last):\n"
        '  File "/usr/bin/pytraceback", line 42, in func1\n'
        "    raise Exception('Test error')\n"
        "Exception: Test error"
    )
    new_oops(30, python_report)
    new_oops(8, python_report)
    new_oops(0, python_report)

    # This new crash is definitely bad, happening everywhere!
    python_report["DistroRelease"] = "Ubuntu 24.04"
    python_report["Package"] = "python3-traceback 1.1"
    python_report["Traceback"] = (
        "Traceback (most recent call last):\n"
        '  File "/usr/bin/pytraceback", line 84, in func2\n'
        "    raise RuntimeError('A very different traceback')\n"
        "RuntimeError: A very different traceback"
    )
    new_oops(2, python_report, systemid="testsystem1")
    new_oops(1, python_report, systemid="testsystem2")
    new_oops(0, python_report, systemid="testsystem3")

    # Even newer crash, less bad this time
    python_report["Package"] = "python3-traceback 1.2"
    python_report["Traceback"] = (
        "Traceback (most recent call last):\n"
        '  File "/usr/bin/pytraceback", line 94, in func3\n'
        "    raise MemoryError('No more memory available, too bad')\n"
        "MemoryError: No more memory available, too bad"
    )
    new_oops(1, python_report)

    schema.SystemImages.objects.create(
        key="device_image", column1="ubuntu-touch/devel-proposed 227 hammerhead", value=b""
    )

    schema.UserBinaryPackages.objects.create(key="foundations-bugs", column1="adduser")
    schema.UserBinaryPackages.objects.create(key="foundations-bugs", column1="apt")
    schema.UserBinaryPackages.objects.create(key="foundations-bugs", column1="util-linux")
    schema.UserBinaryPackages.objects.create(key="xubuntu-bugs", column1="abiword")
    schema.UserBinaryPackages.objects.create(key="daisy-pluckers", column1="failed-retrace")
    schema.UserBinaryPackages.objects.create(key="daisy-pluckers", column1="already-bucketed")
    schema.UserBinaryPackages.objects.create(key="daisy-pluckers", column1="never-crashed")

    # XXX Hack to populate UniqueUsers90Days
    # keep the import here, to avoid a new cassandra setup with the wrong keyspace in the tests
    from tools import unique_users_daily_update

    unique_users_daily_update.main()

    # re-enable daisy logger
    daisy_logger.setLevel(daisy_logger_level)


if __name__ == "__main__":
    from errortracker import cassandra

    cassandra.setup_cassandra()
    create_test_data()
