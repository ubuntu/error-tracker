from datetime import timedelta
from uuid import UUID

import numpy
from pytest import approx

from errors import cassie


class TestCassie:
    def test_get_package_crash_rate_increase_rate(self, datetime_now, cassandra_data):
        now = datetime_now

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "increase-rate",
            "1",
            "2",
            "70",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
        )
        assert crash_rate == approx(
            {
                "increase": True,
                "difference": numpy.float64(4.3),
                "web_link": "https://errors.internal/?release=Ubuntu%2024.04&package=increase-rate&version=2",
                "previous_period_in_days": 30,
                "previous_average": numpy.float64(0.7),
            },
            rel=1e-1,  # We don't want much precision, Cassandra is already messing up the values
        )

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "increase-rate",
            "1",
            "2",
            "70",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
            True,
        )
        assert crash_rate == approx(
            {
                "increase": True,
                "difference": numpy.float64(3.4),
                "web_link": "https://errors.internal/?release=Ubuntu%2024.04&package=increase-rate&version=2",
                "previous_period_in_days": 30,
                "previous_average": numpy.float64(0.7),
            },
            rel=1e-1,  # We don't want much precision, Cassandra is already messing up the values
        )

    def test_get_package_crash_rate_no_crashes_today(self, datetime_now, cassandra_data):
        """Test case where new version has no crashes today - should return increase=False"""
        now = datetime_now

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "no-crashes-today",
            "1",
            "2",
            "100",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
        )
        assert crash_rate == {"increase": False}

    def test_get_package_crash_rate_few_crashes(self, datetime_now, cassandra_data):
        """Test case where new version has only 2 crashes today (less than threshold of 3) - should return increase=False"""
        now = datetime_now

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "few-crashes",
            "1",
            "2",
            "100",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
        )
        assert crash_rate == {"increase": False}

    def test_get_package_crash_rate_new_package(self, datetime_now, cassandra_data):
        """Test case where there's no old version data - should return increase=True with difference=today_crashes"""
        now = datetime_now

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "new-package",
            "0",  # Old version that doesn't exist
            "1",
            "100",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
        )
        assert crash_rate == approx(
            {
                "increase": True,
                "difference": 5,  # Should equal the number of crashes today
                "web_link": "https://errors.internal/?release=Ubuntu%2024.04&package=new-package&version=1",
                "previous_average": None,
            },
            rel=1e-1,
        )

    def test_get_package_crash_rate_low_difference(self, datetime_now, cassandra_data):
        """Test case where crash rate is similar between versions (difference <= 1) - should return increase=False"""
        now = datetime_now

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "low-difference",
            "1",
            "2",
            "100",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
        )
        assert crash_rate == {"increase": False}

    def test_get_package_crash_rate_all_proposed(self, datetime_now, cassandra_data):
        """Test case where all today's crashes are from proposed and we exclude proposed - should return increase=False"""
        now = datetime_now

        crash_rate = cassie.get_package_crash_rate(
            "Ubuntu 24.04",
            "all-proposed",
            "1",
            "2",
            "100",
            (now - timedelta(days=0)).strftime("%Y%m%d"),
            "https://errors.internal/",
            exclude_proposed=True,
        )
        assert crash_rate == {"increase": False}

    def test_bucket_exists_true(self, cassandra_data):
        """Test bucket_exists returns True for existing bucket"""
        assert cassie.bucket_exists("/usr/bin/already-bucketed:11:func1:main") is True

    def test_bucket_exists_false(self, cassandra_data):
        """Test bucket_exists returns False for non-existing bucket"""
        # Use a non-existent bucket ID
        assert cassie.bucket_exists("nonexistent_bucket_12345") is False

    def test_get_crashes_for_bucket(self, cassandra_data):
        """Test get_crashes_for_bucket returns list of crash UUIDs"""
        # Use known bucket from test data
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        crashes = cassie.get_crashes_for_bucket(bucket_id, limit=10)
        assert isinstance(crashes, list)
        # Should have two crashes from the test data
        assert len(crashes) == 2

        for crash in crashes:
            assert isinstance(crash, UUID)

    def test_get_crashes_for_bucket_nonexistent(self, cassandra_data):
        """Test get_crashes_for_bucket returns empty list for non-existent bucket"""
        crashes = cassie.get_crashes_for_bucket("nonexistent_bucket_12345")
        assert crashes == []

    def test_get_metadata_for_bucket(self, cassandra_data):
        """Test get_metadata_for_bucket returns metadata dictionary"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        metadata = cassie.get_metadata_for_bucket(bucket_id)
        assert isinstance(metadata, dict)
        assert metadata["Source"] == "already-bucketed"
        assert metadata["FirstSeen"] == "1.0"
        assert metadata["LastSeen"] == "2.0"
        assert metadata["FirstSeenRelease"] == "Ubuntu 24.04"
        assert metadata["LastSeenRelease"] == "Ubuntu 26.04"

    def test_get_metadata_for_bucket_nonexistent(self, cassandra_data):
        """Test get_metadata_for_bucket returns empty dict for non-existent bucket"""
        metadata = cassie.get_metadata_for_bucket("nonexistent_bucket_12345")
        assert metadata == {}

    def test_get_versions_for_bucket(self, cassandra_data):
        """Test get_versions_for_bucket returns version counts dictionary"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        versions = cassie.get_versions_for_bucket(bucket_id)
        assert isinstance(versions, dict)
        assert versions["Ubuntu 24.04"] == "1.0"
        assert versions["Ubuntu 26.04"] == "2.0"

    def test_get_versions_for_bucket_nonexistent(self, cassandra_data):
        """Test get_versions_for_bucket returns empty dict for non-existent bucket"""
        versions = cassie.get_versions_for_bucket("nonexistent_bucket_12345")
        assert versions == {}

    def test_record_bug_for_bucket_and_get_signatures(self, cassandra_data):
        """Test record_bug_for_bucket records a bug and get_signatures_for_bug retrieves it"""
        from unittest.mock import patch

        from errortracker import config

        bucket_id = "/usr/bin/test-bucket:42:func:main"
        bug_number = 100123

        # Temporarily disable staging mode to test the actual functionality
        with patch.object(config, "lp_use_staging", False):
            # Record a bug for a bucket
            cassie.record_bug_for_bucket(bucket_id, bug_number)

        # Retrieve signatures for that bug
        signatures = cassie.get_signatures_for_bug(bug_number)
        assert isinstance(signatures, list)
        assert signatures == [bucket_id]

    def test_get_signatures_for_bug_nonexistent(self, cassandra_data):
        """Test get_signatures_for_bug returns empty list for non-existent bug"""
        signatures = cassie.get_signatures_for_bug(888888)
        assert signatures == []

    def test_get_crash(self, cassandra_data):
        """Test get_crash returns crash data dictionary"""
        # Get a crash UUID from the test data
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        crashes = cassie.get_crashes_for_bucket(bucket_id, limit=1)
        crash_data = cassie.get_crash(str(crashes[0]))
        assert isinstance(crash_data, dict)
        assert crash_data["ExecutablePath"] == "/usr/bin/already-bucketed"
        assert crash_data["SourcePackage"] == "already-bucketed-src"

    def test_get_crash_nonexistent(self, cassandra_data):
        """Test get_crash returns empty dict for non-existent crash"""
        crash_data = cassie.get_crash("not-a-uuid")
        assert crash_data == {}

    def test_get_package_for_bucket(self, cassandra_data):
        """Test get_package_for_bucket returns package name and version"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        package, version = cassie.get_package_for_bucket(bucket_id)
        assert package == "already-bucketed"
        assert version == "2.0"

    def test_get_package_for_bucket_nonexistent(self, cassandra_data):
        """Test get_package_for_bucket returns empty strings for non-existent bucket"""
        package, version = cassie.get_package_for_bucket("nonexistent_bucket_12345")
        assert package == ""
        assert version == ""

    def test_get_problem_for_hash(self, cassandra_data):
        """Test get_problem_for_hash returns problem signature for hash"""
        # Test with a hash that exists
        result = cassie.get_problem_for_hash("6f2c361a80d2e8afd62563539e9618569e387b48")
        assert result == "/usr/bin/already-bucketed:11:func1:main"

    def test_get_problem_for_hash_nonexistent(self, cassandra_data):
        """Test get_problem_for_hash returns None for non-existent hash"""
        result = cassie.get_problem_for_hash("nonexistent_hash_xyz")
        assert result is None

    def test_get_system_image_versions(self, cassandra_data):
        """Test get_system_image_versions returns list of versions"""
        # Test with a common image type
        versions = cassie.get_system_image_versions("device_image")
        assert versions == ["ubuntu-touch/devel-proposed 227 hammerhead"]

    def test_get_source_package_for_bucket(self, cassandra_data):
        """Test get_source_package_for_bucket returns source package name"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        source_package = cassie.get_source_package_for_bucket(bucket_id)
        assert source_package == "already-bucketed-src"

    def test_get_source_package_for_bucket_nonexistent(self, cassandra_data):
        """Test get_source_package_for_bucket returns empty string for non-existent bucket"""
        source_package = cassie.get_source_package_for_bucket("nonexistent_bucket_12345")
        assert source_package == ""

    def test_get_traceback_for_bucket(self, cassandra_data):
        """Test get_traceback_for_bucket returns traceback data or None"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        traceback = cassie.get_traceback_for_bucket(bucket_id)
        # Traceback field is not in test data, so should return None
        assert traceback is None

    def test_get_traceback_for_bucket_nonexistent(self, cassandra_data):
        """Test get_traceback_for_bucket returns None for non-existent bucket"""
        traceback = cassie.get_traceback_for_bucket("nonexistent_bucket_12345")
        assert traceback is None

    def test_get_stacktrace_for_bucket(self, cassandra_data):
        """Test get_stacktrace_for_bucket returns stacktrace data"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        result = cassie.get_stacktrace_for_bucket(bucket_id)
        # Should return tuple of (Stacktrace, ThreadStacktrace)
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        stacktrace, thread_stacktrace = result
        assert "func1" in stacktrace
        assert "main" in stacktrace

    def test_get_stacktrace_for_bucket_nonexistent(self, cassandra_data):
        """Test get_stacktrace_for_bucket returns (None, None) for non-existent bucket"""
        result = cassie.get_stacktrace_for_bucket("nonexistent_bucket_12345")
        assert result == (None, None)

    def test_get_retrace_failure_for_bucket(self, cassandra_data):
        """Test get_retrace_failure_for_bucket returns failure data"""
        bucket_id = "/usr/bin/already-bucketed:11:func1:main"
        result = cassie.get_retrace_failure_for_bucket(bucket_id)
        # Should return empty dict if no failure data exists
        assert isinstance(result, dict)

    def test_get_retrace_failure_for_bucket_nonexistent(self, cassandra_data):
        """Test get_retrace_failure_for_bucket returns empty dict for non-existent bucket"""
        result = cassie.get_retrace_failure_for_bucket("nonexistent_bucket_12345")
        assert result == {}
