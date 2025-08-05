#!/usr/bin/python

import unittest
import mock
from testtools import TestCase
from oopsrepository.testing.cassandra import TemporaryOOPSDB
import pycassa
import os
import time
from hashlib import sha512

from oopsrepository import schema as oopsschema
from oopsrepository import config as oopsconfig
from daisy import config
from daisy import schema
import datetime
import uuid


class T(TestCase):
    def setUp(self):
        super(T, self).setUp()
        self.start_response = mock.Mock()

        # Set up daisy schema.
        os.environ["OOPS_HOST"] = config.cassandra_hosts[0]
        self.keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        os.environ["OOPS_KEYSPACE"] = self.keyspace
        config.cassandra_keyspace = self.keyspace
        self.creds = {
            "username": config.cassandra_username,
            "password": config.cassandra_password,
        }
        schema.create()

        # Set up oopsrepository schema.
        oops_config = oopsconfig.get_config()
        oops_config["username"] = config.cassandra_username
        oops_config["password"] = config.cassandra_password
        oopsschema.create(oops_config)

    def test_weighting(self):
        """Test the weighting of errors per calendar day.
        The first error ever seen for a system running a given release
        should be 0.
        Subsequent errors should be the number of days since that first
        error, divided by 90, up to 1.0.
        """

        # This has to go here and there can't be any other tests in this file,
        # as these modules set up the Cassandra connections at import time.
        from tools import build_errors_by_release
        from tools import weight_errors_per_day
        from tools import unique_systems_for_errors_by_release

        # Configure the script that back populates the data to use our test
        # Cassandra keyspace for writing data into.
        pool = pycassa.ConnectionPool(
            self.keyspace, config.cassandra_hosts, credentials=self.creds
        )
        build_errors_by_release.write_pool = pool
        args = (pool, "FirstError")
        build_errors_by_release.firsterror = pycassa.ColumnFamily(*args)
        args = (pool, "ErrorsByRelease")
        build_errors_by_release.errorsbyrelease = pycassa.ColumnFamily(*args)
        args = (pool, "SystemsForErrorsByRelease")
        build_errors_by_release.systems = pycassa.ColumnFamily(*args)
        oops = pycassa.ColumnFamily(pool, "OOPS")

        # Create three reports. The first one week ago, the second a single day
        # after the first, and the third a day after that.
        last_week = datetime.datetime.today() - datetime.timedelta(days=7)
        last_week = last_week.replace(hour=0, minute=0, second=0, microsecond=0)
        timestamps = [
            # Convert to microseconds for Cassandra.
            time.mktime(last_week.timetuple()) * 1e6,
            time.mktime((last_week + datetime.timedelta(days=1)).timetuple()) * 1e6,
            time.mktime((last_week + datetime.timedelta(days=2)).timetuple()) * 1e6,
        ]

        # All the reports for this test will be from the same machine, running
        # Ubuntu 12.04.
        ident = sha512("To be filled by OEM").hexdigest()
        for timestamp in timestamps:
            u = str(uuid.uuid1())
            d = {"DistroRelease": "Ubuntu 12.04", "SystemIdentifier": ident}
            oops.insert(u, d, timestamp=timestamp)

        # We will process each error report to find the first occurance for
        # each system for each release. Because we will not process these in
        # time order, we'll need to go through a second time to write the
        # correct values from FirstError (which isn't correct until we've seen
        # all the data) into ErrorsByRelease.
        #
        # As an example, if we see a report from a day ago and write it into
        # FirstError and ErrorsByRelease, then we see a report from a week ago
        # and write it into FirstError and ErrorsByRelease, the data in
        # FirstError will be correct, but that first error report value in
        # ErrorsByRelease will be inaccurate, because it was based on a report
        # from a week ago being the first error report seen for the given
        # release.
        build_errors_by_release.main()
        build_errors_by_release.main()

        # Now actually produce the weights for all of last week (it will only
        # process the three days there were reports).
        start = last_week
        end = datetime.datetime.today()
        unique_systems_for_errors_by_release.main("Ubuntu 12.04", start, end)
        weights = weight_errors_per_day.weight()

        # On the first day we had any error reports, the weighting would be 0
        # because 0 days have passed since the first report.
        self.assertEqual(weights[timestamps[0] / 1e6], 0.0)

        # The second report is one day after the first, and the only report of
        # the day.
        self.assertEqual(weights[timestamps[1] / 1e6], 1 / 90.0)

        # The third report is two days after the first, and the only report of
        # the day.
        self.assertEqual(weights[timestamps[2] / 1e6], 2 / 90.0)


if __name__ == "__main__":
    unittest.main()
