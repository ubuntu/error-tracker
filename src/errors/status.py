"""
This module contains tests to verify that Errors is functioning properly. Any
function that begins with 'check_' will automatically be called as part of the
'/status' URL.
"""

from json import loads

from django.test.client import Client

from errortracker import config

c = Client()


def check_average_crashes():
    response = c.get("/api/1.0/average-crashes/?format=json")
    data = loads(response.content)
    releases = [
        "Ubuntu 22.04 (by 20.04 standards)",
        "Ubuntu 22.04",
        "Ubuntu 24.04 (by 22.04 standards)",
        "Ubuntu 24.04",
        "Ubuntu 26.04 (by 24.04 standards)",
        "Ubuntu 26.04",
        "Ubuntu 26.10 (by 24.04 standards)",
        "Ubuntu 26.10",
    ]
    if releases != [x["key"] for x in data["objects"]]:
        return False
    return True


def check_buckets():
    from django.contrib.auth.models import Group
    from django.test.client import RequestFactory

    from .auth import allowed_teams
    from .views import bucket

    b = (
        "/usr/bin/lsb_release:IOError:<module>:main:"
        "check_modules_installed:getoutput:getstatusoutput"
    )
    rf = RequestFactory()
    req = rf.get("/bucket/", {"id": b})
    # TODO add a mocked version of a user without the correct permissions.
    req.user = Group.objects.get(name=allowed_teams[0]).user_set.all()[0]
    bucket(req)
    return True


def check_most_common_problems():
    url = "/api/1.0/most-common-problems/?limit=100&format=json"
    response = c.get(url)
    data = loads(response.content)
    if len(data["objects"]) == 100:
        obj = data["objects"][0]
        if "count" in obj and "function" in obj:
            return True
    return False


def check_oops_reports():
    try:
        # If we get more than 100 oops reports, alert.
        from errortracker import swift_utils

        if (
            len(
                list(
                    swift_utils.get_swift_client().get_container(
                        container=config.swift_bucket, full_listing=True
                    )
                )
            )
            > 100
        ):
            return False
        else:
            return True
    except OSError:
        # No reports.
        return True
