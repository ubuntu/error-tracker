# -*- coding: utf-8; -*-
# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

import json
import time
import datetime
import uuid
import os

import pycassa
from testtools import TestCase

from oopsrepository import oopses
from oopsrepository import config
from oopsrepository.testing.cassandra import TemporaryOOPSDB


class ClearCache(TestCase):
    def setUp(self):
        super(ClearCache, self).setUp()
        # oopsrepository.oopses has a cache of the connection pool, which we
        # need to clear to prevent previous test runs from bleeding through to
        # the next.
        oopses._connection_pool = None

        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        os.environ["OOPS_KEYSPACE"] = keyspace
        self.config = config.get_config()
        self.pool = pycassa.ConnectionPool(
            self.config["keyspace"],
            self.config["host"],
            username=self.config["username"],
            password=self.config["password"],
        )


class TestPrune(ClearCache):

    def test_fresh_oops_kept(self):
        day_key = oopses.insert(
            self.config, "key", json.dumps({"date": time.time(), "URL": "a bit boring"})
        )
        dayoopses_cf = pycassa.ColumnFamily(self.pool, "DayOOPS")
        oopses_cf = pycassa.ColumnFamily(self.pool, "OOPS")
        oopses.prune(self.config)
        # The oops is still readable and the day hasn't been purged.
        oopses_cf.get("key")
        dayoopses_cf.get(day_key)

    def test_old_oops_deleted(self):
        dayoopses_cf = pycassa.ColumnFamily(self.pool, "DayOOPS")
        datestamp = time.time() - oopses.MONTH - oopses.DAY
        day_key = time.strftime("%Y%m%d", time.gmtime(datestamp))
        now_uuid = uuid.uuid1()
        dayoopses_cf.insert(day_key, {now_uuid: "key"})
        oopses_cf = pycassa.ColumnFamily(self.pool, "OOPS")
        oopses_cf.insert("key", {"date": json.dumps(datestamp), "URL": "a bit boring"})
        oopses.prune(self.config)
        self.assertRaises(pycassa.NotFoundException, oopses_cf.get, "key")
        # The day index is cleared out too.
        self.assertRaises(pycassa.NotFoundException, dayoopses_cf.get, day_key)


class TestInsert(ClearCache):

    def _test_insert_check(self, oopsid, day_key, value=None):
        oopses_cf = pycassa.ColumnFamily(self.pool, "OOPS")
        if value is None:
            value = "13000"
        # The oops is retrievable
        columns = oopses_cf.get(oopsid)
        self.assertEqual(value, columns["duration"])
        # The oops has been indexed by day
        dayoops_cf = pycassa.ColumnFamily(self.pool, "DayOOPS")
        oops_refs = dayoops_cf.get(day_key)
        self.assertEqual([oopsid], list(oops_refs.values()))
        ## TODO - the aggregates for the OOPS have been updated.

    def test_insert_oops(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        oopsid = str(uuid.uuid1())
        oops = json.dumps({"duration": 13000})
        day_key = oopses.insert(self.config, oopsid, oops)
        self._test_insert_check(oopsid, day_key)

    def test_insert_oops_dict(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        oopsid = str(uuid.uuid1())
        oops = {"duration": "13000"}
        day_key = oopses.insert_dict(self.config, oopsid, oops)
        self._test_insert_check(oopsid, day_key)

    def test_insert_unicode(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        oopsid = str(uuid.uuid1())
        oops = {"duration": "♥"}
        day_key = oopses.insert_dict(self.config, oopsid, oops)
        self._test_insert_check(oopsid, day_key, value="♥")

    def test_insert_updates_counters(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        counters_cf = pycassa.ColumnFamily(self.pool, "Counters")
        oopsid = str(uuid.uuid1())
        oops = {"duration": "13000"}
        user_token = "user1"

        day_key = oopses.insert_dict(self.config, oopsid, oops, user_token)
        oops_count = counters_cf.get("oopses", [day_key])
        self.assertEqual([1], list(oops_count.values()))

        oopsid = str(uuid.uuid1())
        day_key = oopses.insert_dict(config, oopsid, oops, user_token)
        oops_count = counters_cf.get("oopses", [day_key])
        self.assertEqual([2], list(oops_count.values()))


class TestBucket(ClearCache):

    def test_insert_bucket(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        fields = [
            "Ubuntu 12.04",
            "Ubuntu 12.04:whoopsie",
            "Ubuntu 12.04:whoopsie:3.04",
            "whoopsie:3.04",
        ]
        oopsid = str(uuid.uuid1())
        oops = json.dumps({"duration": 13000})
        oopses.insert(self.config, oopsid, oops)
        day_key = oopses.bucket(self.config, oopsid, "bucket-key", fields)

        bucket_cf = pycassa.ColumnFamily(self.pool, "Bucket")
        daybucketcount_cf = pycassa.ColumnFamily(self.pool, "DayBucketsCount")

        oops_refs = bucket_cf.get("bucket-key")
        self.assertEqual([pycassa.util.uuid.UUID(oopsid)], list(oops_refs.keys()))
        self.assertEqual(
            list(daybucketcount_cf.get(day_key, ["bucket-key"]).values()), [1]
        )

        oopsid = str(uuid.uuid1())
        oops = json.dumps({"wibbles": 12})
        oopses.insert(self.config, oopsid, oops)
        day_key = oopses.bucket(self.config, oopsid, "bucket-key", fields)

        # Check that the counters all exist and have two crashes.
        resolutions = (day_key[:4], day_key[:6], day_key)
        for field in fields:
            for resolution in resolutions:
                k = "%s:%s" % (field, resolution)
                self.assertEqual(
                    list(daybucketcount_cf.get(k, ["bucket-key"]).values()), [2]
                )
        for resolution in resolutions:
            self.assertEqual(
                list(daybucketcount_cf.get(resolution, ["bucket-key"]).values()), [2]
            )

    def test_update_bucket_metadata(self):
        import apt

        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        bucketmetadata_cf = pycassa.ColumnFamily(self.pool, "BucketMetadata")
        # Does not exist yet.
        oopses.update_bucket_metadata(
            self.config,
            "bucket-id",
            "whoopsie",
            "1.2.3",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = bucketmetadata_cf.get("bucket-id")
        self.assertEqual(metadata["Source"], "whoopsie")
        self.assertEqual(metadata["FirstSeen"], "1.2.3")
        self.assertEqual(metadata["LastSeen"], "1.2.3")
        self.assertEqual(metadata["~Ubuntu 12.04:FirstSeen"], "1.2.3")
        self.assertEqual(metadata["~Ubuntu 12.04:LastSeen"], "1.2.3")

        oopses.update_bucket_metadata(
            config,
            "bucket-id",
            "whoopsie",
            "1.2.4",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = bucketmetadata_cf.get("bucket-id")
        self.assertEqual(metadata["Source"], "whoopsie")
        self.assertEqual(metadata["FirstSeen"], "1.2.3")
        self.assertEqual(metadata["LastSeen"], "1.2.4")
        self.assertEqual(metadata["~Ubuntu 12.04:FirstSeen"], "1.2.3")
        self.assertEqual(metadata["~Ubuntu 12.04:LastSeen"], "1.2.4")

        # Earlier version than the newest
        oopses.update_bucket_metadata(
            config,
            "bucket-id",
            "whoopsie",
            "1.2.4~ev1",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = bucketmetadata_cf.get("bucket-id")
        self.assertEqual(metadata["Source"], "whoopsie")
        self.assertEqual(metadata["FirstSeen"], "1.2.3")
        self.assertEqual(metadata["LastSeen"], "1.2.4")
        self.assertEqual(metadata["~Ubuntu 12.04:FirstSeen"], "1.2.3")
        self.assertEqual(metadata["~Ubuntu 12.04:LastSeen"], "1.2.4")

        # Earlier version than the earliest
        oopses.update_bucket_metadata(
            config,
            "bucket-id",
            "whoopsie",
            "1.2.2",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = bucketmetadata_cf.get("bucket-id")
        self.assertEqual(metadata["Source"], "whoopsie")
        self.assertEqual(metadata["FirstSeen"], "1.2.2")
        self.assertEqual(metadata["LastSeen"], "1.2.4")
        self.assertEqual(metadata["~Ubuntu 12.04:FirstSeen"], "1.2.2")
        self.assertEqual(metadata["~Ubuntu 12.04:LastSeen"], "1.2.4")

    def test_bucket_hashes(self):
        # Test hashing
        from hashlib import sha1

        hashes_cf = pycassa.ColumnFamily(self.pool, "Hashes")
        h = sha1("bucket-id").hexdigest()
        oopses.update_bucket_hashes(self.config, "bucket-id")
        v = list(hashes_cf.get("bucket_%s" % h[0], columns=[h]).values())[0]
        self.assertEqual(v, "bucket-id")

    def test_update_bucket_versions(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        bucketversions_cf = pycassa.ColumnFamily(self.pool, "BucketVersions")
        oopses.update_bucket_versions(self.config, "bucket-id", "1.2.3")
        self.assertEqual(bucketversions_cf.get("bucket-id")["1.2.3"], 1)

        bv_full = pycassa.ColumnFamily(self.pool, "BucketVersionsFull")
        bv_count = pycassa.ColumnFamily(self.pool, "BucketVersionsCount")
        u = uuid.uuid1()
        args = (self.config, "bucket-id", "1.2.3", "Ubuntu 12.04", str(u))
        oopses.update_bucket_versions(*args)
        d = list(bv_full.get(("bucket-id", "Ubuntu 12.04", "1.2.3")).items())[0]
        self.assertEqual((u, ""), d)
        c = bv_count.get("bucket-id", columns=[("Ubuntu 12.04", "1.2.3")])
        c = list(c.values())[0]
        self.assertEqual(1, c)

    def test_dpkg_comparator(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        bv_count = pycassa.ColumnFamily(self.pool, "BucketVersionsCount")
        bv_count.add("bucket-id", ("release", "1.0"))
        bv_count.get("bucket-id", columns=[("release", "1.0")])
        bv_count.get("bucket-id", column_start=[("release", "1.0")])
        bv_count.get("bucket-id", column_finish=[("release", "1.0")])
        bv_count.add("bucket-id", ("release", "1.0~ev1"))
        self.assertEqual(
            1, bv_count.get("bucket-id", column_count=1)[("release", "1.0~ev1")]
        )
        bv_count.add("bucket-id", ("release", "1.0+ev1"))
        c = [("release", "1.0+")]
        self.assertEqual(
            1, bv_count.get("bucket-id", column_start=c)[("release", "1.0+ev1")]
        )

    def test_update_errors_by_release(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        firsterror = pycassa.ColumnFamily(self.pool, "FirstError")
        errorsbyrelease = pycassa.ColumnFamily(self.pool, "ErrorsByRelease")
        release = "Ubuntu 12.04"
        system_token = "system-id"
        oops_id = uuid.uuid1()
        today = datetime.datetime.today()
        today = today.replace(hour=0, minute=0, second=0, microsecond=0)
        oopses.update_errors_by_release(self.config, oops_id, system_token, release)

        d = firsterror.get(release, columns=[system_token])[system_token]
        self.assertEqual(today, d)
        d = list(errorsbyrelease.get((release, today)).values())[0]
        self.assertEqual(today, d)

    def test_update_source_version_buckets(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        srcversbuckets = pycassa.ColumnFamily(self.pool, "SourceVersionBuckets")
        src_package = "whoopsie"
        version = "1.2.3"
        oops_id = str(uuid.uuid1())
        oopses.update_source_version_buckets(self.config, src_package, version, oops_id)

        bucket_id = list(srcversbuckets.get((src_package, version)).keys())[0]
        self.assertEqual(oops_id, bucket_id)

    def test_update_bucket_systems(self):
        keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        bv_systems = pycassa.ColumnFamily(self.pool, "BucketVersionSystems2")
        bucketid = "foo"
        system_token = "system-id"
        version = "1.0"
        oopses.update_bucket_systems(
            self.config, bucketid, system_token, version=version
        )

        system = list(bv_systems.get((bucketid, version)).keys())[0]
        self.assertEqual(system, system_token)
