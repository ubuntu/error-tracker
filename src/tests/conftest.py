# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""Test helpers for working with cassandra."""

import shutil
import tempfile
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
