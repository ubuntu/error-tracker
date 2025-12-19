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
