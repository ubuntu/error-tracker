# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

import os

from pycassa.system_manager import SystemManager
from testtools import TestCase

from oopsrepository import config
from oopsrepository.testing.cassandra import TemporaryKeyspace, TemporaryOOPSDB
from oopsrepository.testing.matchers import HasOOPSSchema


class TestTemporaryKeyspace(TestCase):

    def test_manages_keyspace(self):
        fixture = TemporaryKeyspace()
        with fixture:
            os.environ["OOPS_KEYSPACE"] = fixture.keyspace
            c = config.get_config()
            creds = {"username": c["username"], "password": c["password"]}
            mgr = SystemManager(c["host"][0], credentials=creds)
            keyspace = fixture.keyspace
            # The keyspace should be accessible.
            self.assertTrue(keyspace in mgr.list_keyspaces())
        # And deleted after the fixture is finished with.
        self.assertFalse(keyspace in mgr.list_keyspaces())


class TestTemporaryOOPSDB(TestCase):

    def test_usable(self):
        with TemporaryOOPSDB() as db:
            keyspace = db.keyspace
            self.assertThat(keyspace, HasOOPSSchema())
