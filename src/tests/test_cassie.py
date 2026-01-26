from datetime import datetime, timedelta
from uuid import UUID

import distro_info
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
                "difference": numpy.float64(4.7),
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
        """Test get_traceback_for_bucket returns traceback data"""
        bucket_id = "/usr/bin/pytraceback:Exception:func1"
        traceback = cassie.get_traceback_for_bucket(bucket_id)
        assert "Traceback (most recent call last)" in traceback
        assert "/usr/bin/pytraceback" in traceback
        assert "Test error" in traceback

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
        # Check specific values in stacktrace
        assert "func1" in stacktrace
        assert "main" in stacktrace
        # Check specific values in thread_stacktrace
        assert "Thread 1" in thread_stacktrace
        assert "0x42424242" in thread_stacktrace
        assert "func1 ()" in thread_stacktrace
        assert "already-bucketed.c:42" in thread_stacktrace

    def test_get_stacktrace_for_bucket_nonexistent(self, cassandra_data):
        """Test get_stacktrace_for_bucket returns (None, None) for non-existent bucket"""
        result = cassie.get_stacktrace_for_bucket("nonexistent_bucket_12345")
        assert result == (None, None)

    def test_get_retrace_failure_for_bucket(self, cassandra_data):
        """Test get_retrace_failure_for_bucket returns failure data"""
        bucket_id = "/usr/bin/failed-retrace:11:failed_func:main"
        result = cassie.get_retrace_failure_for_bucket(bucket_id)
        # Should return dict with failure reasons
        assert isinstance(result, dict)
        assert len(result) > 0
        assert "missing-debug-symbols" in result
        assert "Debug symbols not available" in result["missing-debug-symbols"]
        assert "retrace-error" in result
        assert "Failed to generate stacktrace" in result["retrace-error"]

    def test_get_retrace_failure_for_bucket_nonexistent(self, cassandra_data):
        """Test get_retrace_failure_for_bucket returns empty dict for non-existent bucket"""
        result = cassie.get_retrace_failure_for_bucket("nonexistent_bucket_12345")
        assert result == {}

    def test_get_metadata_for_buckets(self, cassandra_data):
        """Test get_metadata_for_buckets returns metadata for multiple buckets"""
        bucket_ids = [
            "/usr/bin/already-bucketed:11:func1:main",
            "/usr/bin/failed-retrace:11:failed_func:main",
        ]
        metadata = cassie.get_metadata_for_buckets(bucket_ids)
        assert isinstance(metadata, dict)
        assert len(metadata) == 2
        assert metadata["/usr/bin/already-bucketed:11:func1:main"]["Source"] == "already-bucketed"
        assert (
            metadata["/usr/bin/failed-retrace:11:failed_func:main"]["Source"] == "failed-retrace"
        )

    def test_get_metadata_for_buckets_empty(self, cassandra_data):
        """Test get_metadata_for_buckets returns empty dict for empty list"""
        metadata = cassie.get_metadata_for_buckets([])
        assert metadata == {}

    def test_get_user_crashes(self, cassandra_data):
        """Test get_user_crashes returns list of crash UUIDs for a user"""
        # Using the test system ID from create_test_data
        user_token = "imatestsystem"
        crashes = cassie.get_user_crashes(user_token, limit=5)
        assert isinstance(crashes, list)
        assert len(crashes) == 5
        for uuid_str, crash_time in crashes:
            assert isinstance(uuid_str, str)
            assert isinstance(crash_time, datetime)
        first_crash = crashes[0]
        more_crashes = cassie.get_user_crashes(user_token, limit=5, start=first_crash[0])
        assert len(crashes) == 5
        assert crashes[1] == more_crashes[0]
        assert crashes[2] == more_crashes[1]
        assert more_crashes[-1] not in crashes

    def test_get_user_crashes_nonexistent(self, cassandra_data):
        """Test get_user_crashes returns empty list for non-existent user"""
        crashes = cassie.get_user_crashes("nonexistent_user_12345")
        assert crashes == []

    def test_get_binary_packages_for_user(self, cassandra_data):
        """Test get_binary_packages_for_user returns list of packages or None"""
        packages = cassie.get_binary_packages_for_user("daisy-pluckers")
        assert packages == ["already-bucketed", "failed-retrace"]

    def test_get_binary_packages_for_user_no_crash(self, cassandra_data):
        """Test get_binary_packages_for_user returns None when user has no binary packages"""
        packages = cassie.get_binary_packages_for_user("foundations-bugs")
        assert packages == []

    def test_get_binary_packages_for_user_non_existing_user(self, cassandra_data):
        """Test get_binary_packages_for_user returns None when user has no binary packages"""
        packages = cassie.get_binary_packages_for_user("nonexistent_user_12345")
        assert packages is None

    def test_get_package_new_buckets(self, cassandra_data):
        """Test get_package_new_buckets returns list of new crash buckets"""
        buckets = cassie.get_package_new_buckets("python-traceback", "1.0", "1.1")
        assert buckets == ["/usr/bin/pytraceback:RuntimeError:func2"]
        buckets = cassie.get_package_new_buckets("python-traceback", "1.1", "1.2")
        assert buckets == []

    def test_get_package_new_buckets_nonexistent(self, cassandra_data):
        """Test get_package_new_buckets returns empty list for non-existent package"""
        buckets = cassie.get_package_new_buckets("nonexistent_package", "1.0", "2.0")
        assert buckets == []

    def test_get_oopses_by_day(self, datetime_now, cassandra_data):
        """Test get_oopses_by_day returns list of OOPS IDs for the given day"""
        yesterday = (datetime_now - timedelta(days=1)).strftime("%Y%m%d")
        oopses = list(cassie.get_oopses_by_day(yesterday))
        assert len(oopses) == 8
        assert all(isinstance(oops, UUID) for oops in oopses)
        oopses = list(cassie.get_oopses_by_day(yesterday, limit=6))
        assert len(oopses) == 6
        a_week_ago = (datetime_now - timedelta(days=7)).strftime("%Y%m%d")
        oopses = list(cassie.get_oopses_by_day(a_week_ago))
        assert len(oopses) == 1

    def test_get_oopses_by_day_no_data(self, cassandra_data):
        """Test get_oopses_by_day returns empty list for a day with no crashes"""
        future_date = "20991231"  # Far future date with no crashes
        oopses = list(cassie.get_oopses_by_day(future_date))
        assert oopses == []

    def test_get_oopses_by_release(self, cassandra_data):
        """Test get_oopses_by_release returns list of OOPS IDs for the given release"""
        oopses = list(cassie.get_oopses_by_release("Ubuntu 24.04"))
        assert len(oopses) == 81
        assert all(isinstance(oops, UUID) for oops in oopses)
        oopses = list(cassie.get_oopses_by_release("Ubuntu 24.04", limit=6))
        assert len(oopses) == 6

    def test_get_oopses_by_release_no_data(self, cassandra_data):
        """Test get_oopses_by_release returns empty list for a release with no crashes"""
        oopses = list(cassie.get_oopses_by_release("Ubuntu 99.99"))
        assert oopses == []

    def test_get_total_buckets_by_day(self, cassandra_data):
        """Test get_total_buckets_by_day returns date and count tuples"""
        results = list(cassie.get_total_buckets_by_day(0, 7))
        assert len(results) == 7
        assert results[0][1] == 4
        assert results[1][1] == 2
        assert results[2][1] == 1
        assert results[-1][1] == 0
        for date, count in results:
            assert isinstance(date, str)
            assert len(date) == 8  # YYYYMMDD format
            assert isinstance(count, int)
        results = list(cassie.get_total_buckets_by_day(30, 31))
        assert len(results) == 1
        assert results[0][1] == 1

    def test_get_bucket_counts(self, datetime_now, cassandra_data):
        """Test get_bucket_counts returns list of (bucket_id, count) tuples"""
        results = cassie.get_bucket_counts(release="Ubuntu 24.04", period="week")
        assert results == [
            (b"/usr/bin/pytraceback:RuntimeError:func2", 3),
            (b"/usr/bin/pytraceback:MemoryError:func3", 1),
            (b"/usr/bin/already-bucketed:11:func1:main", 1),
            (b"/usr/bin/failed-retrace:11:failed_func:main", 1),
            (b"/usr/bin/pytraceback:Exception:func1", 1),
        ]

    def test_get_bucket_counts_no_data(self, cassandra_data):
        """Test get_bucket_counts returns empty list when no data matches"""
        results = cassie.get_bucket_counts(release="Ubuntu 99.99", period="day")
        assert results == []

    def test_get_retracer_count(self, datetime_now, cassandra_data, retracer):
        """Test get_retracer_count returns dictionary of retrace statistics"""
        release = "Ubuntu 24.04"
        yesterday = (datetime_now - timedelta(days=1)).strftime("%Y%m%d")
        retracer.update_retrace_stats(release, yesterday, 30, True)
        result = cassie.get_retracer_count(yesterday)
        assert result == {"Ubuntu 24.04:amd64": {"success": 1}, "Ubuntu 24.04": {"success": 1}}

    def test_get_retracer_count_no_data(self, cassandra_data):
        """Test get_retracer_count returns empty dict for date with no stats"""
        result = cassie.get_retracer_count("20991231")
        assert result == {}

    def test_get_retracer_counts(self, datetime_now, cassandra_data, retracer):
        """Test get_retracer_counts returns generator of (date, stats) tuples"""
        release = "Ubuntu 24.04"
        yesterday = (datetime_now - timedelta(days=1)).strftime("%Y%m%d")
        three_days_ago = (datetime_now - timedelta(days=3)).strftime("%Y%m%d")
        retracer.update_retrace_stats(release, yesterday, 30, True)
        retracer.update_retrace_stats(release, three_days_ago, 30, True)
        retracer.update_retrace_stats(release, three_days_ago, 30, True)
        results = list(cassie.get_retracer_counts(0, 7))
        assert isinstance(results[0][0], str)
        assert len(results[0][0]) == 8  # YYYYMMDD format
        assert results[1][1] == {
            "Ubuntu 24.04:amd64": {"success": 2},
            "Ubuntu 24.04": {"success": 2},
        }
        assert results[3][1] == {
            "Ubuntu 24.04:amd64": {"success": 2},
            "Ubuntu 24.04": {"success": 2},
        }

    def test_get_retracer_means(self, datetime_now, cassandra_data, retracer):
        """Test get_retracer_means returns list of (date, release_arch_dict) tuples"""
        release = distro_info.UbuntuDistroInfo().lts(result="release")
        release = "Ubuntu " + release.replace(" LTS", "")
        yesterday = (datetime_now - timedelta(days=1)).strftime("%Y%m%d")
        three_days_ago = (datetime_now - timedelta(days=3)).strftime("%Y%m%d")
        retracer.update_retrace_stats(release, yesterday, 30, True)
        retracer.update_retrace_stats(release, three_days_ago, 20, True)
        retracer.update_retrace_stats(release, three_days_ago, 60, True)
        results = cassie.get_retracer_means(1, 4)
        assert isinstance(results[0][0], str)
        assert len(results[0][0]) == 8  # YYYYMMDD format
        assert results[0][1][release]["amd64"] == 30.0
        assert results[2][1][release]["amd64"] == 35.0

    def test_get_crash_count(self, datetime_now, cassandra_data):
        """Test get_crash_count returns generator of (date, count) tuples"""
        results = list(cassie.get_crash_count(0, 7))
        assert isinstance(results[0][0], str)
        assert len(results[0][0]) == 8  # YYYYMMDD format
        assert results[0][1] == 20
        assert results[2][1] == 7

    def test_get_crash_count_with_release(self, datetime_now, cassandra_data):
        """Test get_crash_count with release parameter returns filtered results"""
        results = list(cassie.get_crash_count(0, 7, release="Ubuntu 24.04"))
        assert isinstance(results[0][0], str)
        assert len(results[0][0]) == 8  # YYYYMMDD format
        assert results[0][1] == 19
        assert results[2][1] == 7
        results = list(cassie.get_crash_count(0, 7, release="Ubuntu 26.04"))
        assert results[0][1] == 1
        assert len(results) == 1

    def test_get_average_crashes(self, datetime_now, cassandra_data):
        """Test get_average_crashes returns list of (timestamp, average) tuples"""
        yesterday = datetime_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=1
        )
        result = cassie.get_average_crashes("python3-traceback", "Ubuntu 24.04", days=7)
        assert result[0][0] == int(yesterday.timestamp())
        assert result[0][1] == approx(0.666666666)

    def test_get_average_crashes_no_data(self, cassandra_data):
        """Test get_average_crashes returns empty list when no data exists"""
        result = cassie.get_average_crashes("python3-traceback", "Ubuntu 99.99", days=7)
        assert result == []

    def test_get_average_instances(self, datetime_now, cassandra_data):
        """Test get_average_instances returns generator of (timestamp, average) tuples"""
        yesterday = datetime_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=1
        )
        result = list(
            cassie.get_average_instances(
                "/usr/bin/pytraceback:RuntimeError:func2", "Ubuntu 24.04", days=7
            )
        )
        assert result[0][0] == int(yesterday.timestamp())
        assert result[0][1] == approx(0.333333333)

    def test_get_average_instances_no_data(self, cassandra_data):
        """Test get_average_instances returns empty list for non-existent bucket"""
        result = list(cassie.get_average_instances("nonexistent", "Ubuntu 24.04", days=7))
        assert result == []
