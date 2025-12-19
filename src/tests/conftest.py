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
    # fmt: on

    # re-enable daisy logger
    daisy_logger.setLevel(daisy_logger_level)

    yield
