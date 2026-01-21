from datetime import timedelta

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
