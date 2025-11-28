"""
This module contains tests to verify that Errors is functioning properly. Any
function that begins with 'check_' will automatically be called as part of the
'/status' URL.
"""

import datetime
import os
from json import loads

from django.test.client import Client

from daisy import config

c = Client()


def check_average_crashes():
    response = c.get("/api/1.0/average-crashes/?format=json")
    data = loads(response.content)
    releases = [
        "Ubuntu 12.04",
        "Ubuntu 12.10 (by 12.04 standards)",
        "Ubuntu 12.10",
        "Ubuntu 13.04 (by 12.04 standards)",
        "Ubuntu 13.04",
        "Ubuntu 13.10 (by 12.04 standards)",
        "Ubuntu 13.10",
        "Ubuntu 14.04 (by 12.04 standards)",
        "Ubuntu 14.04",
        "Ubuntu 14.10 (by 14.04 standards)",
        "Ubuntu 14.10",
        "Ubuntu 15.04 (by 14.04 standards)",
        "Ubuntu 15.04",
        "Ubuntu 15.10 (by 14.04 standards)",
        "Ubuntu 15.10",
        "Ubuntu 16.04 (by 14.04 standards)",
        "Ubuntu 16.04",
        "Ubuntu 16.10 (by 16.04 standards)",
        "Ubuntu 16.10",
        "Ubuntu 17.04 (by 16.04 standards)",
        "Ubuntu 17.04",
        "Ubuntu 17.10 (by 16.04 standards)",
        "Ubuntu 17.10",
        "Ubuntu 18.04 (by 16.04 standards)",
        "Ubuntu 18.04",
        "Ubuntu 18.10 (by 18.04 standards)",
        "Ubuntu 18.10",
        "Ubuntu 19.04 (by 18.04 standards)",
        "Ubuntu 19.04",
        "Ubuntu 19.10 (by 18.04 standards)",
        "Ubuntu 19.10",
        "Ubuntu 20.04 (by 18.04 standards)",
        "Ubuntu 20.04",
        "Ubuntu 20.10 (by 20.04 standards)",
        "Ubuntu 20.10",
        "Ubuntu 21.04 (by 20.04 standards)",
        "Ubuntu 21.04",
        "Ubuntu 21.10 (by 20.04 standards)",
        "Ubuntu 21.10",
        "Ubuntu 22.04 (by 20.04 standards)",
        "Ubuntu 22.04",
        "Ubuntu 22.10 (by 22.04 standards)",
        "Ubuntu 22.10",
        "Ubuntu 23.04 (by 22.04 standards)",
        "Ubuntu 23.04",
        "Ubuntu 23.10 (by 22.04 standards)",
        "Ubuntu 23.10",
        "Ubuntu 24.04 (by 22.04 standards)",
        "Ubuntu 24.04",
        "Ubuntu 24.10 (by 24.04 standards)",
        "Ubuntu 24.10",
        "Ubuntu 25.04 (by 24.04 standards)",
        "Ubuntu 25.04",
        "Ubuntu 25.10 (by 24.04 standards)",
        "Ubuntu 25.10",
        "Ubuntu 26.04 (by 24.04 standards)",
        "Ubuntu 26.04",
    ]
    if releases != [x["key"] for x in data["objects"]]:
        return False
    return True


def check_buckets():
    from django.contrib.auth.models import Group
    from django.test.client import RequestFactory

    from .views import bucket

    b = (
        "/usr/bin/lsb_release:IOError:<module>:main:"
        "check_modules_installed:getoutput:getstatusoutput"
    )
    rf = RequestFactory()
    req = rf.get("/bucket/", {"id": b})
    # TODO add a mocked version of a user without the correct permissions.
    req.user = Group.objects.get(name="daisy-pluckers").user_set.all()[0]
    bucket(req)
    return True


def check_most_common_problems():
    url = "/api/1.0/most-common-problems/?limit=100&format=json"
    response = c.get(url)
    data = loads(response.content)
    l = len(data["objects"])
    if l == 100:
        obj = data["objects"][0]
        if "count" in obj and "function" in obj:
            return True
    return False


def check_oops_reports():
    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        l = os.listdir(os.path.join(config.oops_repository, today))
        # If we get more than 25 oops reports, alert.
        if len(l) > 25:
            return False
        else:
            return True
    except OSError:
        # No reports.
        return True
