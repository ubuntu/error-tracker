import locale
import logging
from datetime import datetime, timedelta

import bson

from daisy.submit import submit


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
        new_oops(i,  {"DistroRelease": "Ubuntu 24.04", "Package": "increase-rate 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/increase-rate", "StacktraceAddressSignature": "/usr/bin/increase-rate:42:/usr/bin/increase-rate+fa0"})

    # increase-rate package version 2 in proposed, even more crashes!
    for i in [1, 0]:
        new_oops(i,  {"DistroRelease": "Ubuntu 24.04", "Package": "increase-rate 2", "ProblemType": "Crash", "Architecture": "amd64", "ExecutablePath": "/usr/bin/increase-rate", "StacktraceAddressSignature": "/usr/bin/increase-rate:42:/usr/bin/increase-rate+fa0", "Tags": "package-from-proposed"})

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

    # re-enable daisy logger
    daisy_logger.setLevel(daisy_logger_level)


if __name__ == "__main__":
    from errortracker import cassandra

    cassandra.setup_cassandra()
    create_test_data()
