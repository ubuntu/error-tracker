# -*- coding: utf8 -*-
import datetime

# Actually show the messages (info) with the retracer format.
import logging
import os
import shutil
import tempfile
import time
import unittest
import uuid

import amqp
import mock
import pycassa
from pycassa.types import FloatType, IntegerType
from testtools import TestCase

from daisy import config, retracer, schema
from oopsrepository import config as oopsconfig
from oopsrepository import schema as oopsschema
from oopsrepository.testing.cassandra import TemporaryOOPSDB

logging.basicConfig(format=retracer.LOGGING_FORMAT, level=logging.INFO)


class TestSubmission(TestCase):
    def setUp(self):
        super(TestSubmission, self).setUp()
        # We need to set the config before importing.
        os.environ["OOPS_HOST"] = config.cassandra_hosts[0]
        self.keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        os.environ["OOPS_KEYSPACE"] = self.keyspace
        creds = {
            "username": config.cassandra_username,
            "password": config.cassandra_password,
        }
        self.pool = pycassa.ConnectionPool(
            self.keyspace, config.cassandra_hosts, credentials=creds
        )
        config.cassandra_keyspace = self.keyspace
        schema.create()
        oops_config = oopsconfig.get_config()
        oops_config["username"] = config.cassandra_username
        oops_config["password"] = config.cassandra_password
        oopsschema.create(oops_config)
        self.temp = tempfile.mkdtemp()
        config_dir = os.path.join(self.temp, "config")
        sandbox_dir = os.path.join(self.temp, "sandbox")
        os.makedirs(config_dir)
        os.makedirs(sandbox_dir)
        self.architecture = "amd64"
        # Don't depend on apport-retrace being installed.
        with mock.patch("daisy.retracer.Popen") as popen:
            popen.return_value.returncode = 0
            popen.return_value.communicate.return_value = ["/bin/false"]
            self.retracer = retracer.Retracer(
                config_dir, sandbox_dir, self.architecture, False, False
            )

    def tearDown(self):
        super(TestSubmission, self).tearDown()
        shutil.rmtree(self.temp)

    def test_update_retrace_stats(self):
        retrace_stats_fam = pycassa.ColumnFamily(self.pool, "RetraceStats")
        indexes_fam = pycassa.ColumnFamily(self.pool, "Indexes")
        release = "Ubuntu 12.04"
        day_key = time.strftime("%Y%m%d", time.gmtime())

        self.retracer.update_retrace_stats(release, day_key, 30.5, True)
        result = retrace_stats_fam.get(day_key)
        self.assertEqual(result["Ubuntu 12.04:success"], 1)
        mean_key = "%s:%s:%s" % (day_key, release, self.architecture)
        counter_key = "%s:count" % mean_key
        indexes_fam.column_validators = {
            mean_key: FloatType(),
            counter_key: IntegerType(),
        }
        result = indexes_fam.get("mean_retracing_time")
        self.assertEqual(result[mean_key], 30.5)
        self.assertEqual(result[counter_key], 1)

        self.retracer.update_retrace_stats(release, day_key, 30.5, True)
        result = indexes_fam.get("mean_retracing_time")
        self.assertEqual(result[mean_key], 30.5)
        self.assertEqual(result[counter_key], 2)

    def test_chunked_insert(self):
        # UnicodeEncodeError: 'ascii' codec can't encode character u'\xe9' in
        # position 487: ordinal not in range(128)
        stack_fam = pycassa.ColumnFamily(self.pool, "Stacktrace")
        stack_fam.default_validation_class = pycassa.types.UTF8Type()

        # Non-chunked version.
        data = {"Package": "apport", "ProblemType": "Crash"}
        retracer.chunked_insert(stack_fam, "foo", data)
        results = next(stack_fam.get_range())
        self.assertEqual(results[0], "foo")
        self.assertEqual(results[1]["Package"], "apport")
        self.assertEqual(results[1]["ProblemType"], "Crash")

        # Chunked.
        stack_fam.truncate()
        data["Big"] = "a" * (1024 * 1024 * 4 + 1)
        retracer.chunked_insert(stack_fam, "foo", data)
        results = next(stack_fam.get_range())
        self.assertEqual(results[0], "foo")
        self.assertEqual(results[1]["Package"], "apport")
        self.assertEqual(results[1]["ProblemType"], "Crash")
        self.assertEqual(results[1]["Big"], "a" * 1024 * 1024 * 4)
        self.assertEqual(results[1]["Big-1"], "a")

        # Unicode. As generated in callback(), oops_fam.get()
        stack_fam.truncate()
        data = {"☃".encode("utf8"): "☕".encode("utf8")}
        retracer.chunked_insert(stack_fam, "foo", data)
        results = next(stack_fam.get_range())

    def test_retracer_logging(self):
        msg = mock.Mock()
        u = uuid.uuid1()
        msg.body = "%s:%s" % (str(u), "local")
        from io import StringIO

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        root.handlers = []
        try:
            root.addHandler(handler)
            with mock.patch.object(retracer, "config") as cfg:
                cfg.core_storage = {"local": {"type": "local", "path": "/tmp"}}
                path = os.path.join("/tmp", str(u))
                with open(path, "w") as fp:
                    fp.write("fake core file")
                self.retracer.callback(msg)
                self.assertFalse(os.path.exists(path))

            # Test that pycassa can still log correctly.
            self.retracer.pool.listeners[0].logger.info("pycassa-message")
        finally:
            # Don't leave logging set up.
            root.handlers = []
        stream.seek(0)
        contents = stream.read()
        self.assertIn("%s:%s" % (str(u), "local"), contents)
        self.assertIn(":pycassa.pool:pycassa-message", contents)

    def test_update_time_to_retrace(self):
        time_to_retrace = pycassa.ColumnFamily(self.pool, "TimeToRetrace")

        oops_id = str(uuid.uuid1())
        ts = datetime.datetime.utcnow()
        ts = ts - datetime.timedelta(minutes=5)

        msg = amqp.Message(oops_id, timestamp=ts)

        self.retracer.update_time_to_retrace(oops_id, msg)
        date, vals = next(time_to_retrace.get_range())
        day_key = time.strftime("%Y%m%d", time.gmtime())
        self.assertEqual(date, day_key)
        # Tolerate it being 9.9 seconds off at most.
        self.assertAlmostEqual(vals[oops_id], 60 * 5, places=-1)


if __name__ == "__main__":
    unittest.main()
