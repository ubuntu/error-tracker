# -*- coding: utf-8; -*-
# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

import datetime
import json
import time
import uuid

import pytest
from cassandra.cqlengine.query import DoesNotExist

from errortracker import cassandra_schema, oopses


class TestPrune:
    def test_fresh_oops_kept(self, temporary_db):
        ts = time.time()
        day_key = oopses.insert_dict("key", {"date": json.dumps(ts), "URL": "a bit boring"})

        # Prune OOPSes
        oopses.prune()

        # The oops is still readable and the day hasn't been purged.
        oops = cassandra_schema.OOPS.get_as_dict(key=b"key")
        assert oops == {"date": str(ts), "URL": "a bit boring"}
        dayoopses = cassandra_schema.DayOOPS.filter(key=day_key.encode())
        found = False
        for dayoops in dayoopses:
            if dayoops.value.decode() == "key":
                found = True
        assert found is True, "DayOOPS object not found"

    def test_old_oops_deleted(self, temporary_db):
        ts = time.time()
        very_old_date = ts - 90 * oopses.DAY
        old_date = ts - 31 * oopses.DAY
        not_old_date = ts - 20 * oopses.DAY
        very_old_day_key = time.strftime("%Y%m%d", time.gmtime(very_old_date))
        old_day_key = time.strftime("%Y%m%d", time.gmtime(old_date))
        not_old_day_key = time.strftime("%Y%m%d", time.gmtime(not_old_date))
        data = [
            {
                "datestamp": very_old_date,
                "day_key": very_old_day_key,
                "key": "very_old_key",
                "URL": "very boring",
            },
            {
                "datestamp": old_date,
                "day_key": old_day_key,
                "key": "old_key",
                "URL": "boring",
            },
            {
                "datestamp": not_old_date,
                "day_key": not_old_day_key,
                "key": "not_old_key",
                "URL": "not boring",
            },
        ]
        for oops in data:
            cassandra_schema.DayOOPS.create(
                key=oops["day_key"].encode(), column1=uuid.uuid1(), value=oops["key"].encode()
            )
            cassandra_schema.OOPS.create(
                key=oops["key"].encode(), column1="date", value=json.dumps(oops["datestamp"])
            )
            cassandra_schema.OOPS.create(
                key=oops["key"].encode(), column1="URL", value=oops["URL"]
            )

        # Prune OOPSes
        oopses.prune()

        with pytest.raises(DoesNotExist) as _:
            cassandra_schema.OOPS.get(key=b"very_old_key")
        with pytest.raises(DoesNotExist) as _:
            cassandra_schema.OOPS.get(key=b"old_key")
        assert (
            cassandra_schema.OOPS.get(key=b"not_old_key", column1="URL").value == "not boring"
        ), "OOPS was pruned, but was too recent"
        # The day index is cleared out too.
        with pytest.raises(DoesNotExist) as _:
            cassandra_schema.DayOOPS.get(key=very_old_day_key.encode())
        with pytest.raises(DoesNotExist) as _:
            cassandra_schema.DayOOPS.get(key=old_day_key.encode())
        assert (
            cassandra_schema.DayOOPS.get(key=not_old_day_key.encode()).value.decode()
            == "not_old_key"
        )


class TestInsert:
    def _test_insert_check(self, oopsid, day_key, value=None):
        if value is None:
            value = "13000"
        # The oops is retrievable
        result = cassandra_schema.OOPS.get_as_dict(key=oopsid.encode())
        assert value == result["duration"]
        # The oops has been indexed by day
        oops_refs = cassandra_schema.DayOOPS.filter(key=day_key.encode()).only(["value"])
        assert oopsid in [day_oops.value.decode() for day_oops in oops_refs]
        # TODO - the aggregates for the OOPS have been updated.

    def test_insert_oops_dict(self, temporary_db):
        oopsid = str(uuid.uuid1())
        oops = {"duration": "13000"}
        day_key = oopses.insert_dict(oopsid, oops)
        self._test_insert_check(oopsid, day_key)

    def test_insert_unicode(self, temporary_db):
        oopsid = str(uuid.uuid1())
        oops = {"duration": "♥"}
        day_key = oopses.insert_dict(oopsid, oops)
        self._test_insert_check(oopsid, day_key, value="♥")

    def test_insert_updates_counters(self, temporary_db):
        oopsid = str(uuid.uuid1())
        oops = {"duration": "13000"}
        user_token = "user1"

        day_key = oopses.insert_dict(oopsid, oops, user_token)
        oops_count = cassandra_schema.Counters.filter(key=b"oopses", column1=day_key)
        assert [3] == [count.value for count in oops_count]

        oopsid = str(uuid.uuid1())
        day_key = oopses.insert_dict(oopsid, oops, user_token)
        oops_count = cassandra_schema.Counters.filter(key=b"oopses", column1=day_key)
        assert [4] == [count.value for count in oops_count]

    def test_insert_updates_errorsbyrelease(self, temporary_db):
        oopsid = str(uuid.uuid1())
        oops = {"DistroRelease": "Ubuntu 42.42", "Date": "Tue Jan 20 14:01:54 2026"}
        user_token = "user1"

        oopses.insert_dict(oopsid, oops, user_token)
        result = list(cassandra_schema.ErrorsByRelease.filter(key="Ubuntu 42.42"))
        assert len(result) == 1
        assert result[0].value == datetime.datetime(2026, 1, 20, 14, 1, 54)


class TestBucket:
    def test_insert_bucket(self, temporary_db):
        fields = [
            "Ubuntu 12.04",
            "Ubuntu 12.04:whoopsie",
            "Ubuntu 12.04:whoopsie:3.04",
            "whoopsie:3.04",
        ]
        oopsid = str(uuid.uuid1())
        oops = json.dumps({"duration": 13000})
        oopses.insert(oopsid, oops)
        day_key = oopses.bucket(oopsid, "bucket-key", fields)

        assert [oopsid] == [
            str(bucket_entry.column1)
            for bucket_entry in cassandra_schema.Bucket.filter(key="bucket-key")
        ]
        assert [1] == [
            counter.value
            for counter in cassandra_schema.DayBucketsCount.filter(
                key=day_key.encode(), column1="bucket-key"
            )
        ]

        oopsid = str(uuid.uuid1())
        oops = json.dumps({"wibbles": 12})
        oopses.insert(oopsid, oops)
        day_key = oopses.bucket(oopsid, "bucket-key", fields)

        # Check that the counters all exist and have two crashes.
        resolutions = (day_key[:4], day_key[:6], day_key)
        for field in fields:
            for resolution in resolutions:
                k = "%s:%s" % (field, resolution)
                assert [2] == [
                    counter.value
                    for counter in cassandra_schema.DayBucketsCount.filter(
                        key=k.encode(), column1="bucket-key"
                    )
                ]
        for resolution in resolutions:
            assert [2] == [
                counter.value
                for counter in cassandra_schema.DayBucketsCount.filter(
                    key=resolution.encode(), column1="bucket-key"
                )
            ]

    def test_update_bucket_metadata(self, temporary_db):
        import apt

        # Does not exist yet.
        oopses.update_bucket_metadata(
            "bucket-id",
            "whoopsie",
            "1.2.3",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = cassandra_schema.BucketMetadata.get_as_dict(key=b"bucket-id")
        assert metadata["Source"] == "whoopsie"
        assert metadata["FirstSeen"] == "1.2.3"
        assert metadata["LastSeen"] == "1.2.3"
        assert metadata["~Ubuntu 12.04:FirstSeen"] == "1.2.3"
        assert metadata["~Ubuntu 12.04:LastSeen"] == "1.2.3"

        oopses.update_bucket_metadata(
            "bucket-id",
            "whoopsie",
            "1.2.4",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = cassandra_schema.BucketMetadata.get_as_dict(key=b"bucket-id")
        assert metadata["Source"] == "whoopsie"
        assert metadata["FirstSeen"] == "1.2.3"
        assert metadata["LastSeen"] == "1.2.4"
        assert metadata["~Ubuntu 12.04:FirstSeen"] == "1.2.3"
        assert metadata["~Ubuntu 12.04:LastSeen"] == "1.2.4"

        # Earlier version than the newest
        oopses.update_bucket_metadata(
            "bucket-id",
            "whoopsie",
            "1.2.4~ev1",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = cassandra_schema.BucketMetadata.get_as_dict(key=b"bucket-id")
        assert metadata["Source"] == "whoopsie"
        assert metadata["FirstSeen"] == "1.2.3"
        assert metadata["LastSeen"] == "1.2.4"
        assert metadata["~Ubuntu 12.04:FirstSeen"] == "1.2.3"
        assert metadata["~Ubuntu 12.04:LastSeen"] == "1.2.4"

        # Earlier version than the earliest
        oopses.update_bucket_metadata(
            "bucket-id",
            "whoopsie",
            "1.2.2",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.04",
        )
        metadata = cassandra_schema.BucketMetadata.get_as_dict(key=b"bucket-id")
        assert metadata["Source"] == "whoopsie"
        assert metadata["FirstSeen"] == "1.2.2"
        assert metadata["LastSeen"] == "1.2.4"
        assert metadata["~Ubuntu 12.04:FirstSeen"] == "1.2.2"
        assert metadata["~Ubuntu 12.04:LastSeen"] == "1.2.4"

        # Same crash in newer Ubuntu release
        oopses.update_bucket_metadata(
            "bucket-id",
            "whoopsie",
            "1.2.4",
            apt.apt_pkg.version_compare,
            "Ubuntu 12.10",
        )
        metadata = cassandra_schema.BucketMetadata.get_as_dict(key=b"bucket-id")
        assert metadata["Source"] == "whoopsie"
        assert metadata["FirstSeen"] == "1.2.2"
        assert metadata["LastSeen"] == "1.2.4"
        assert metadata["~Ubuntu 12.04:FirstSeen"] == "1.2.2"
        assert metadata["~Ubuntu 12.04:LastSeen"] == "1.2.4"
        assert metadata["~Ubuntu 12.10:FirstSeen"] == "1.2.4"
        assert metadata["~Ubuntu 12.10:LastSeen"] == "1.2.4"

    def test_bucket_hashes(self, temporary_db):
        # Test hashing
        from hashlib import sha1

        h = sha1(b"bucket-id").hexdigest()
        oopses.update_bucket_hashes("bucket-id")
        assert (
            "bucket-id"
            == cassandra_schema.Hashes.get(key=f"bucket_{h[0]}".encode(), column1=h.encode()).value
        )

    def test_update_source_version_buckets(self, temporary_db):
        src_package = "whoopsie"
        version = "1.2.3"
        oops_id = str(uuid.uuid1())
        oopses.update_source_version_buckets(src_package, version, oops_id)

        assert (
            oops_id
            == cassandra_schema.SourceVersionBuckets.get(key=src_package, key2=version).column1
        )

    def test_update_bucket_systems(self, temporary_db):
        bucketid = "foo"
        system_token = "system-id"
        version = "1.0"
        oopses.update_bucket_systems(bucketid, system_token, version=version)

        assert (
            system_token
            == cassandra_schema.BucketVersionSystems2.get(key=bucketid, key2=version).column1
        )
