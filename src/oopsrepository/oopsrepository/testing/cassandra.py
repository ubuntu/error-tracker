# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""Test helpers for working with cassandra."""

import os
import os.path

from fixtures import Fixture, TempDir
import pycassa
from pycassa.system_manager import SystemManager

from oopsrepository.cassandra_shim import workaround_1779
from oopsrepository.schema import create
from oopsrepository.config import get_config


class TemporaryKeyspace(Fixture):
    """Create a temporary keyspace.

    The keyspace is named after a tempdir.
    """

    def setUp(self):
        super(TemporaryKeyspace, self).setUp()
        tempdir = self.useFixture(TempDir())
        self.keyspace = os.path.basename(tempdir.path)
        os.environ['OOPS_KEYSPACE'] = self.keyspace
        c = get_config()
        creds = {'username': c['username'], 'password': c['password']}
        self.mgr = SystemManager(c['host'][0], credentials=creds)
        workaround_1779(self.mgr.create_keyspace, self.keyspace,
            pycassa.SIMPLE_STRATEGY, {'replication_factor' : '1'})
        self.addCleanup(workaround_1779, self.mgr.drop_keyspace,
            self.keyspace)


class TemporaryOOPSDB(Fixture):
    """Create a temporary usable OOPS DB.
    
    The keyspace for it is at self.keyspace.
    """

    def setUp(self):
        super(TemporaryOOPSDB, self).setUp()
        self.keyspace = self.useFixture(TemporaryKeyspace()).keyspace
        os.environ['OOPS_KEYSPACE'] = self.keyspace
        create(get_config())
