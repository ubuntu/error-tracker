import datetime
import time
import urllib.parse
from uuid import UUID

import distro_info
import numpy
from cassandra.util import datetime_from_uuid1

from errortracker import cassandra, config
from errortracker.cassandra_schema import (
    OOPS,
    Bucket,
    BucketMetadata,
    BucketRetraceFailureReason,
    BucketVersionsCount,
    BucketVersionSystems2,
    BugToCrashSignatures,
    Counters,
    CountersForProposed,
    DayBucketsCount,
    DayOOPS,
    DoesNotExist,
    ErrorsByRelease,
    Hashes,
    Indexes,
    RetraceStats,
    SourceVersionBuckets,
    Stacktrace,
    SystemImages,
    UniqueUsers90Days,
    UserBinaryPackages,
    UserOOPS,
)

session = cassandra.cassandra_session


def _split_into_dictionaries(original):
    value = {}
    for k in original:
        name, result = k.rsplit(":", 1)
        value.setdefault(name, {})
        value[name][result] = original[k]
    return value


def _get_range_of_dates(start_x_days_ago: int, finish_x_days_ago: int) -> list[str]:
    """Get a range of dates from start to finish.
    This is necessary because we use the Cassandra random partitioner, so
    lexicographical ranges are not possible."""
    finish_x_days_ago = finish_x_days_ago - start_x_days_ago
    date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=start_x_days_ago)
    delta = datetime.timedelta(days=1)
    dates = []
    for i in range(finish_x_days_ago):
        dates.append(date.strftime("%Y%m%d"))
        date = date - delta
    return dates


def get_oopses_by_day(date: str, limit: int = 1000):
    """All of the OOPSes in the given day."""
    for row in DayOOPS.objects.filter(key=date.encode()).limit(limit):
        yield row.column1


def get_oopses_by_release(release: str, limit: int = 1000):
    """All of the OOPSes in the given release."""
    for row in ErrorsByRelease.objects.filter(key=release).limit(limit):
        yield row.column1


def get_total_buckets_by_day(start: int, finish: int):
    """All of the buckets added to for the past seven days."""
    dates = _get_range_of_dates(start, finish)
    for date in dates:
        count = DayBucketsCount.objects.filter(key=date.encode()).count()
        yield (date, count)


def _date_range_iterator(start, finish):
    # Iterate all the values including and between the start and finish date
    # string.
    start = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:]))
    finish = datetime.date(int(finish[:4]), int(finish[4:6]), int(finish[6:]))
    while start <= finish:
        yield start.strftime("%Y%m%d")
        start += datetime.timedelta(days=1)


def get_bucket_counts(
    release=None,
    package=None,
    version=None,
    pkg_arch=None,
    rootfs_build_version=None,
    channel_name=None,
    device_name=None,
    device_image_version=None,
    period=None,
    batch_size=100,
    show_failed=False,
    from_date=None,
    to_date=None,
):
    """The number of times each bucket has been added to today, this month, or
    this year."""

    periods = ""
    if period:
        if period == "today" or period == "day":
            period = datetime.date.today().strftime("%Y%m%d")
        elif period == "week":
            week_end = datetime.date.today().strftime("%Y%m%d")
            week_start = datetime.date.today() - datetime.timedelta(days=7)
            week_start = week_start.strftime("%Y%m%d")
            periods = [x for x in _date_range_iterator(week_start, week_end)]
        elif period == "month":
            period = datetime.date.today().strftime("%Y%m")
        elif period == "year":
            period = datetime.date.today().strftime("%Y")
        if not periods:
            periods = [period]
    elif from_date and to_date:
        periods = [x for x in _date_range_iterator(from_date, to_date)]
    else:
        # Just use today.
        periods = [datetime.date.today().strftime("%Y%m%d")]

    # Will need to change if one wants to look up a release and
    # rootfs_build_version or device_image_version
    if rootfs_build_version:
        releases = [rootfs_build_version]
    elif channel_name:
        if device_name:
            releases = ["%s:%s" % (channel_name, device_name)]
        else:
            releases = [channel_name]
    elif device_image_version:
        releases = [device_image_version]
    elif release:
        releases = [release]
    else:
        # FIXME supported releases should not be hard-coded
        releases = [
            "Ubuntu 14.04",
            "Ubuntu 16.04",
            "Ubuntu 18.04",
            "Ubuntu 20.04",
            "Ubuntu 22.04",
            "Ubuntu 24.04",
            "Ubuntu 25.04",
            "Ubuntu 25.10",
            "Ubuntu 26.04",
        ]

    keys = []
    for period in periods:
        for release in releases:
            key = [x for x in (release, package, version, pkg_arch, period) if x]
            key = ":".join(key)
            keys.append(key)

    results = {}
    for key in keys:
        try:
            rows = DayBucketsCount.objects.filter(key=key.encode()).all()
            for row in rows:
                column = row.column1
                count = row.value
                if not show_failed and column.startswith("failed"):
                    continue
                if isinstance(column, str):
                    column = column.encode("utf-8")
                try:
                    existing = results[column]
                except KeyError:
                    existing = 0
                results[column] = count + existing
        except DoesNotExist:
            continue

    return sorted(list(results.items()), key=lambda x: x[1], reverse=True)


def get_crashes_for_bucket(bucketid: str, limit: int = 100, start: str = None) -> list[UUID]:
    """
    Get limit crashes for the provided bucket, starting at start.

    We show the most recent crashes first, since they'll be the most
    relevant to the current state of the problem.
    """
    try:
        query = Bucket.objects.filter(key=bucketid).order_by("-column1")
        if start:
            start_uuid = UUID(start)
            # Get items less than start (because of reversed ordering)
            query = query.filter(column1__lt=start_uuid)

        return [row.column1 for row in list(query.limit(limit).all())]
    except DoesNotExist:
        return []


def get_package_for_bucket(bucketid):
    """Returns the package and version for a given bucket."""

    # Grab 50 OOPS IDs, just in case the first one doesn't have a Package field.
    try:
        rows = Bucket.objects.filter(key=bucketid).limit(50).all()
        oopsids = [row.column1 for row in rows]
    except DoesNotExist:
        return ("", "")

    for oopsid in oopsids:
        try:
            oops_rows = OOPS.objects.filter(key=str(oopsid).encode(), column1="Package").all()
            for row in oops_rows:
                value = row.value
                if isinstance(value, bytes):
                    value = value.decode("utf-8")
                package_and_version = value.split()[:2]
                if len(package_and_version) == 1:
                    return (package_and_version[0], "")
                else:
                    return tuple(package_and_version)
        except (KeyError, DoesNotExist):
            continue
    return ("", "")


def get_crash(oopsid, columns=None):
    try:
        query = OOPS.objects.filter(key=oopsid.encode())
        if columns:
            # Filter by specific columns
            query = query.filter(column1__in=columns)

        oops = {}
        for row in query.all():
            oops[row.column1] = row.value

        if not oops:
            return {}
    except DoesNotExist:
        return {}

    if "StacktraceAddressSignature" in oops:
        SAS = oops["StacktraceAddressSignature"]
        if not SAS:
            return oops
    # TODO sort out finding the crash_sig for a DuplicateSignature or Traceback
    elif "DuplicateSignature" in oops:
        SAS = oops["DuplicateSignature"]
        oops["SAS"] = SAS
        return oops
    else:
        return oops

    try:
        index_key = b"crash_signature_for_stacktrace_address_signature"
        index_rows = Indexes.objects.filter(key=index_key, column1=SAS).all()
        for row in index_rows:
            oops["SAS"] = row.value.decode() if isinstance(row.value, bytes) else row.value
            break
        return oops
    except DoesNotExist:
        return oops


def get_traceback_for_bucket(bucketid):
    # TODO fetching a crash ID twice, once here and once in get_stacktrace, is
    # a bit rubbish, but we'll write the stacktrace into the bucket at some
    # point and get rid of the contents of both of these functions.
    crashes = get_crashes_for_bucket(bucketid, 1)
    if len(crashes) == 0:
        return None
    crash = str(crashes[0])
    try:
        rows = OOPS.objects.filter(key=crash.encode(), column1="Traceback").all()
        for row in rows:
            return row.value
        return None
    except DoesNotExist:
        return None


def get_stacktrace_for_bucket(bucketid: str):
    # TODO: we should build some sort of index for this.
    SAS = "StacktraceAddressSignature"
    cols = ["Stacktrace", "ThreadStacktrace"]
    for crash in get_crashes_for_bucket(bucketid, 10):
        sas = None
        try:
            rows = OOPS.objects.filter(key=str(crash).encode(), column1=SAS).all()
            for row in rows:
                sas = row.value
                break
        except DoesNotExist:
            pass
        if not sas:
            continue
        try:
            traces = {}
            for col in cols:
                trace_rows = Stacktrace.objects.filter(key=sas.encode(), column1=col).all()
                for row in trace_rows:
                    traces[col] = row.value
            return (traces.get("Stacktrace", None), traces.get("ThreadStacktrace", None))
        except DoesNotExist:
            pass
    return (None, None)


def get_retracer_count(date: str):
    try:
        result = RetraceStats.get_as_dict(key=date.encode())
        return _split_into_dictionaries(result)
    except DoesNotExist:
        return {}


def get_retracer_counts(start, finish):
    dates = _get_range_of_dates(start, finish)
    results = {}
    for date in dates:
        try:
            result = RetraceStats.get_as_dict(key=date.encode())
            results[date] = result
        except DoesNotExist:
            pass
    return ((date, _split_into_dictionaries(results[date])) for date in results)


def get_retracer_means(start, finish):
    dates = _get_range_of_dates(start, finish)
    results = list()
    for date in dates:
        result = {}
        for release in distro_info.UbuntuDistroInfo().supported(result="object"):
            release = "Ubuntu " + release.version.replace(" LTS", "")
            result[release] = {}
            for arch in ["amd64", "arm64", "armhf", "i386"]:
                try:
                    key = f"{date}:{release}:{arch}"
                    timings = Indexes.get_as_dict(key=b"mean_retracing_time", column1=key)
                    result[release][arch] = timings[key]
                except (DoesNotExist, IndexError):
                    pass
        results.append((date, result))
    return results


def get_crash_count(start, finish, release=None):
    dates = _get_range_of_dates(start, finish)
    for date in dates:
        try:
            if release:
                key = "oopses:%s" % release
            else:
                key = "oopses"
            rows = Counters.objects.filter(key=key.encode(), column1=date).all()
            for row in rows:
                oopses = int(row.value)
                yield (date, oopses)
                break
        except DoesNotExist:
            pass


def get_metadata_for_bucket(bucketid: str, release: str = None):
    try:
        if not release:
            # Get all columns up to "~" (non-inclusive)
            rows = BucketMetadata.objects.filter(key=bucketid.encode(), column1__lt="~").all()
        else:
            rows = BucketMetadata.objects.filter(key=bucketid.encode()).all()

        ret = {}
        for row in rows:
            ret[row.column1] = row.value

        if release and ret:
            try:
                ret["FirstSeen"] = ret["~%s:FirstSeen" % release]
            except KeyError:
                pass
            try:
                ret["LastSeen"] = ret["~%s:LastSeen" % release]
            except KeyError:
                pass
        return ret
    except DoesNotExist:
        return {}


def get_metadata_for_buckets(bucketids, release=None):
    ret = dict()
    for bucketid in bucketids:
        ret[bucketid] = get_metadata_for_bucket(bucketid, release)
    return ret


def get_user_crashes(user_token: str, limit: int = 50, start=None):
    results = {}
    try:
        query = UserOOPS.objects.filter(key=user_token.encode()).limit(limit).order_by("-column1")

        if start:
            # Filter to get items lower than start (reverse order)
            query = query.filter(column1__lt=start)

        for row in query:
            # Since we don't have timestamp directly, we'll use the column1 to compute it
            results[row.column1] = datetime_from_uuid1(UUID(row.column1))
    except DoesNotExist:
        return []

    return [(k, results[k]) for k in results.keys()]


def get_average_crashes(field, release, days=7):
    dates = _get_range_of_dates(0, days)
    start = dates[-1]
    end = dates[0]

    try:
        key = "oopses:%s" % field
        oopses = dict()
        oops_rows = Counters.objects.filter(
            key=key.encode(), column1__gte=start, column1__lte=end
        ).all()
        for row in oops_rows:
            oopses[row.column1] = row.value

        users = dict()
        user_rows = UniqueUsers90Days.objects.filter(
            key=release, column1__gte=start, column1__lte=end
        ).all()
        for row in user_rows:
            users[row.column1] = row.value
    except DoesNotExist:
        return []

    return_data = []
    for date in oopses:
        try:
            avg = float(oopses[date]) / float(users[date])
        except (ZeroDivisionError, KeyError):
            continue
        t = int(time.mktime(time.strptime(date, "%Y%m%d")))
        return_data.append((t, avg))
    return return_data


def get_average_instances(bucketid, release, days=7):
    # FIXME Why oh why did we do things this way around? It makes it impossible
    # to do a quick range scan. We should create DayBucketsCount2, replacing
    # this with a CF that's keyed on the bucket ID and has counter columns
    # named by the date.
    dates = _get_range_of_dates(0, days)
    start = dates[-1]
    end = dates[0]

    user_rows = UniqueUsers90Days.objects.filter(
        key=release, column1__gte=start, column1__lte=end
    ).all()
    users = {row.column1: row.value for row in user_rows}

    for date in dates:
        try:
            key = "%s:%s" % (release, date)
            count_rows = DayBucketsCount.objects.filter(key=key.encode(), column1=bucketid).all()
            count = None
            for row in count_rows:
                count = row.value
                break
            if count is None:
                continue
        except DoesNotExist:
            continue
        try:
            avg = float(count) / float(users[date])
        except (ZeroDivisionError, KeyError):
            continue
        t = int(time.mktime(time.strptime(date, "%Y%m%d")))
        yield ((t, avg))


def get_versions_for_bucket(bucketid: str):
    """Get the dictionary of (release, version) tuples for the given bucket
    with values of their instance counts. If the bucket does not exist,
    return an empty dict."""
    try:
        rows = BucketVersionsCount.objects.filter(key=bucketid).all()
        result = {}
        for row in rows:
            result[row.column1] = row.column2
        return result
    except DoesNotExist:
        return {}


def get_source_package_for_bucket(bucketid: str):
    bucket_rows = Bucket.objects.filter(key=bucketid).limit(50).all()
    oopsids = [row.column1 for row in bucket_rows]
    for oopsid in oopsids:
        try:
            oops_rows = OOPS.objects.filter(
                key=str(oopsid).encode(), column1="SourcePackage"
            ).all()
            for row in oops_rows:
                return row.value
        except (KeyError, DoesNotExist):
            continue
    return ""


def get_retrace_failure_for_bucket(bucketid: str):
    try:
        failuredata = BucketRetraceFailureReason.get_as_dict(key=bucketid.encode())
        return failuredata
    except DoesNotExist:
        return {}


def get_binary_packages_for_user(user):
    # query DayBucketsCount to ensure the package has crashes reported about
    # it rather than returning packages for which there will be no data.
    # if a package's last crash was reported more than a month ago then it
    # won't be returned here, however the package isn't likely to appear in
    # the most-common-problems.
    last_month = (datetime.date.today() - datetime.timedelta(30)).strftime("%Y%m")
    current_month = (datetime.date.today()).strftime("%Y%m")
    binary_packages = []
    try:
        pkg_rows = UserBinaryPackages.objects.filter(key=user).all()
        binary_packages = [row.column1 for row in pkg_rows]
    except DoesNotExist:
        return None
    if len(binary_packages) == 0:
        return None

    results = []
    for pkg in binary_packages:
        count = (
            DayBucketsCount.objects.filter(key=(pkg + ":%s" % last_month).encode())
            .limit(1)
            .count()
            + DayBucketsCount.objects.filter(key=(pkg + ":%s" % current_month).encode())
            .limit(1)
            .count()
        )
        # only include packages that have recent crashes
        if count > 0:
            results.append(pkg)

    return results


def get_package_crash_rate(
    release, src_package, old_version, new_version, pup, date, absolute_uri, exclude_proposed=False
):
    """Find the rate of Crashes, not other problems, about a package."""

    # the generic counter only includes Crashes for packages from official
    # Ubuntu sources and from systems not under auto testing
    old_vers_column = "oopses:Crash:%s:%s:%s" % (release, src_package, old_version)
    new_vers_column = "oopses:Crash:%s:%s:%s" % (release, src_package, new_version)
    results = {}

    try:
        old_rows = (
            Counters.objects.filter(key=old_vers_column.encode(), column1__lte=date)
            .order_by("-column1")
            .limit(15)
            .all()
        )
        old_vers_data = {row.column1: row.value for row in old_rows}
    except DoesNotExist:
        old_vers_data = None

    try:
        # this may be unnecessarily long since updates phase in ~3 days
        new_rows = (
            Counters.objects.filter(key=new_vers_column.encode())
            .order_by("-column1")
            .limit(15)
            .all()
        )
        new_vers_data = {row.column1: row.value for row in new_rows}
    except DoesNotExist:
        results["increase"] = False
        return results

    if not new_vers_data:
        results["increase"] = False
        return results

    if exclude_proposed:
        try:
            proposed_old_rows = (
                CountersForProposed.objects.filter(key=old_vers_column.encode(), column1__lte=date)
                .order_by("-column1")
                .limit(15)
                .all()
            )
            proposed_old_vers_data = {row.column1: row.value for row in proposed_old_rows}
        except DoesNotExist:
            proposed_old_vers_data = None
        try:
            proposed_new_rows = (
                CountersForProposed.objects.filter(key=new_vers_column.encode())
                .order_by("-column1")
                .limit(15)
                .all()
            )
            proposed_new_vers_data = {row.column1: row.value for row in proposed_new_rows}
        except DoesNotExist:
            proposed_new_vers_data = None

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    try:
        today_crashes = new_vers_data[today]
    except KeyError:
        # no crashes today so not an increase
        results["increase"] = False
        return results

    # subtract CountersForProposed data from today crashes
    if exclude_proposed and proposed_new_vers_data:
        try:
            today_proposed_crashes = proposed_new_vers_data[today]
        except KeyError:
            today_proposed_crashes = 0
        today_crashes = today_crashes - today_proposed_crashes
        if today_crashes == 0:
            # no crashes today so not an increase
            results["increase"] = False
            return results

    if new_vers_data and not old_vers_data:
        results["increase"] = True
        results["previous_average"] = None
        # no previous version data so the diff is today's amount
        results["difference"] = today_crashes
        web_link = "?release=%s&package=%s&version=%s" % (
            urllib.parse.quote(release),
            urllib.parse.quote(src_package),
            urllib.parse.quote(new_version),
        )
        results["web_link"] = absolute_uri + web_link
        return results

    first_date = date
    oldest_date = list(old_vers_data.keys())[-1]
    dates = [x for x in _date_range_iterator(oldest_date, first_date)]
    previous_vers_crashes = []
    previous_days = len(dates[:-1])
    for day in dates[:-1]:
        # subtract CountersForProposed data from previous_vers_crashes
        if exclude_proposed and proposed_old_vers_data:
            try:
                date_proposed_crashes = proposed_old_vers_data[day]
            # the day doesn't exist so there were 0 errors
            except KeyError:
                date_proposed_crashes = 0
        else:
            date_proposed_crashes = 0
        try:
            previous_vers_crashes.append(old_vers_data[day] - date_proposed_crashes)
        # the day doesn't exist so there were 0 errors
        except KeyError:
            previous_vers_crashes.append(0)

    results["increase"] = False
    # 2 crashes may be a fluke
    if today_crashes < 3:
        return results

    now = datetime.datetime.now(datetime.timezone.utc)
    hour = float(now.hour)
    minute = float(now.minute)
    mean_crashes = numpy.average(previous_vers_crashes)
    standard_crashes = (mean_crashes + numpy.std(previous_vers_crashes)).round()
    # if an update isn't fully phased then the previous package version will
    # generally have more crashes than the phasing one so multiple the quanity
    # of crashes by the phasing percentage
    if pup:
        standard_crashes = (standard_crashes * int(pup)) / 100
    # FIXME: Given that release week will see these increase wildly, I wonder
    # if it would be suitable to divide by the number of unique systems that
    # report errors for this package and release combination. Don't we already
    # do this with the graph on the problem page?
    # multiply the standard amount of crashes by the portion of the day that
    # has passed
    difference = today_crashes - (standard_crashes * ((hour * 60 + minute) / (24 * 60)))
    if difference > 1:
        results["increase"] = True
        results["difference"] = difference
        web_link = "?release=%s&package=%s&version=%s" % (
            urllib.parse.quote(release),
            urllib.parse.quote(src_package),
            urllib.parse.quote(new_version),
        )
        results["web_link"] = absolute_uri + web_link
        results["previous_period_in_days"] = previous_days
        results["previous_average"] = standard_crashes
    return results


def get_package_new_buckets(src_pkg: str, previous_version: str, new_version: str):
    results = []

    # new version has no buckets
    try:
        new_rows = SourceVersionBuckets.objects.filter(key=src_pkg, key2=new_version).all()
        n_data = [row.column1 for row in new_rows]
    except (KeyError, DoesNotExist):
        return results

    # if previous version has no buckets return an empty list
    try:
        prev_rows = SourceVersionBuckets.objects.filter(key=src_pkg, key2=previous_version).all()
        p_data = [row.column1 for row in prev_rows]
    except (KeyError, DoesNotExist):
        p_data = []

    new_buckets = set(n_data).difference(set(p_data))
    for bucket in new_buckets:
        # do not return buckets that failed to retrace
        if bucket.startswith("failed:"):
            continue

        try:
            count = BucketVersionSystems2.objects.filter(key=bucket, key2=new_version).count()
        except DoesNotExist:
            continue
        if count <= 2:
            continue
        results.append(bucket)
    return results


def record_bug_for_bucket(bucketid: str, bug: int):
    # We don't insert bugs into the database if we're using Launchpad staging,
    # as those will disappear in Launchpad but our copy would persist.
    if config.lp_use_staging:
        return
    BucketMetadata.create(key=bucketid.encode(), column1="CreatedBug", value=str(bug))
    BugToCrashSignatures.create(key=bug, column1=bucketid, value=b"")


def get_signatures_for_bug(bug: int):
    try:
        rows = BugToCrashSignatures.objects.filter(key=bug).all()
        crashes = [row.column1 for row in rows]
        return crashes
    except DoesNotExist:
        return []


def bucket_exists(bucketid):
    try:
        count = Bucket.objects.filter(key=bucketid).limit(1).count()
        return count > 0
    except DoesNotExist:
        return False


def get_problem_for_hash(hashed: str):
    try:
        key = ("bucket_%s" % hashed[0]).encode()
        rows = Hashes.objects.filter(key=key, column1=hashed.encode()).all()
        for row in rows:
            return row.value
        return None
    except DoesNotExist:
        return None


def get_system_image_versions(image_type: str):
    try:
        rows = SystemImages.objects.filter(key=image_type).limit(None).all()
        versions = set([row.column1 for row in rows])
        return list(versions)
    except DoesNotExist:
        return None
