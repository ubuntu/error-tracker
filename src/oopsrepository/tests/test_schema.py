# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.


from testtools import TestCase
import os

from oopsrepository import schema
from oopsrepository import config
from oopsrepository.testing.cassandra import TemporaryKeyspace
from oopsrepository.testing.matchers import HasOOPSSchema


class TestCreateSchema(TestCase):

    def test_creates_columnfamily(self):
        keyspace = self.useFixture(TemporaryKeyspace()).keyspace
        os.environ["OOPS_KEYSPACE"] = keyspace
        schema.create(config.get_config())
        self.assertThat(keyspace, HasOOPSSchema())
