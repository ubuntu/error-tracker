# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

import os

from testtools import TestCase

from oopsrepository import config, schema
from oopsrepository.testing.cassandra import TemporaryKeyspace
from oopsrepository.testing.matchers import HasOOPSSchema


class TestHasOOPSSchema(TestCase):

    def test_creates_columnfamily(self):
        keyspace = self.useFixture(TemporaryKeyspace()).keyspace
        self.assertNotEqual(None, HasOOPSSchema().match(keyspace))
        os.environ["OOPS_KEYSPACE"] = keyspace
        schema.create(config.get_config())
        self.assertThat(keyspace, HasOOPSSchema())
