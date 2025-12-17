# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""Test helpers for working with cassandra."""

import locale
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from cassandra.cqlengine import management

import retracer as et_retracer
from errortracker import cassandra


@pytest.fixture(scope="function")
def temporary_db():
    cassandra.KEYSPACE = "tmp"
    cassandra.REPLICATION_FACTOR = 1
    cassandra.setup_cassandra()
    yield
    management.drop_keyspace(cassandra.KEYSPACE)


@pytest.fixture(scope="function")
def retracer(temporary_db):
    temp = Path(tempfile.mkdtemp())
    config_dir = temp / "config"
    sandbox_dir = temp / "sandbox"
    config_dir.mkdir()
    sandbox_dir.mkdir()
    architecture = "amd64"
    # Don't depend on apport-retrace being installed.
    with patch("retracer.Popen") as popen:
        popen.return_value.returncode = 0
        popen.return_value.communicate.return_value = ["/bin/false"]
        yield et_retracer.Retracer(
            config_dir=config_dir,
            sandbox_dir=sandbox_dir,
            architecture=architecture,
        )
    shutil.rmtree(temp)


@pytest.fixture(scope="module")
def datetime_now():
    return datetime.now()


@pytest.fixture(scope="function")
def cassandra_data(datetime_now, temporary_db):
    import bson
    import logging

    from daisy.submit import submit

    # disable daisy logger temporarily
    daisy_logger = logging.getLogger("daisy")
    daisy_logger_level = daisy_logger.level
    daisy_logger.setLevel(51)  # CRITICAL is 50, so let's go higher

    # Make sure the datetime will get formatted "correctly" in that cursed time format: Mon May  5 14:46:10 2025
    locale.setlocale(locale.LC_ALL, "C.UTF-8")

    def count():
        counter = 0
        while True:
            yield str(counter)
            counter += 1

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

    yield
