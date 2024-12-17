# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

from unittest import TestLoader


def test_suite():
    test_names = [
        "cassandra_fixture",
        "config",
        "matchers",
        "oopses",
        "schema",
    ]
    tests = ["oopsrepository.tests.test_" + test for test in test_names]
    loader = TestLoader()
    return loader.loadTestsFromNames(tests)
