# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

from fixtures import EnvironmentVariableFixture
from testtools import TestCase

from oopsrepository import config


class TestConfig(TestCase):

    def test_environmentvariables_setting(self):
        with EnvironmentVariableFixture('OOPS_KEYSPACE', 'foo'):
            self.assertEqual('foo', config.get_config()['keyspace'])

    def test_unset_variables_raise(self):
        with EnvironmentVariableFixture('OOPS_KEYSPACE'):
            self.assertRaises(Exception, config.get_config)
