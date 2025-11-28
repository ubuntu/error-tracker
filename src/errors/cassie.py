import datetime
import operator
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import cmp_to_key

import numpy

# TODO: port that to the cassandra module
# import pycassa
# from pycassa.cassandra.ttypes import NotFoundException
# from pycassa.util import OrderedDict
from errortracker import cassandra, config

session = cassandra.cassandra_session()


def _split_into_dictionaries(original):
    value = {}
    for k in original:
        name, result = k.rsplit(":", 1)
        value.setdefault(name, {})
        value[name][result] = original[k]
    return value


def _get_range_of_dates(start, finish):
    """Get a range of dates from start to finish.
    This is necessary because we use the Cassandra random partitioner, so
    lexicographical ranges are not possible."""
    finish = finish - start
    date = datetime.datetime.utcnow() - datetime.timedelta(days=start)
    delta = datetime.timedelta(days=1)
    dates = []
    for i in range(finish):
        dates.append(date.strftime("%Y%m%d"))
        date = date - delta
    return dates


def get_oopses_by_day(date, limit=1000):
    """All of the OOPSes in the given day."""
    oopses_by_day = session.prepare('SELECT value FROM crashdb."DayOOPS" WHERE key = ? LIMIT ?;')
    for row in session.execute(oopses_by_day, [date, limit]):
        yield row.value


def get_oopses_by_release(release, limit=1000):
    """All of the OOPSes in the given release."""
    oopses_by_release = session.prepare(
        'SELECT column1 FROM crashdb."ErrorsByRelease" WHERE key = ? LIMIT ? ALLOW FILTERING;'
    )
    for row in session.execute(oopses_by_release, [release.encode(), limit]):
        yield row.column1


def get_total_buckets_by_day(start, finish):
    """All of the buckets added to for the past seven days."""
    daybucketscount_cf = pycassa.ColumnFamily(pool, "DayBucketsCount")
    dates = _get_range_of_dates(start, finish)
    for date in dates:
        yield (date, daybucketscount_cf.get_count(date))


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

    daybucketscount_cf = pycassa.ColumnFamily(pool, "DayBucketsCount")
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
    batch_size = 500
    for key in keys:
        start = ""
        while True:
            try:
                result = daybucketscount_cf.get(key, column_start=start, column_count=batch_size)
            except NotFoundException:
                break

            for column, count in result.items():
                if not show_failed and column.startswith("failed"):
                    continue
                column = column.encode("utf-8")
                try:
                    existing = results[column]
                except KeyError:
                    existing = 0
                results[column] = count + existing
            # We do not want to include the end of the previous batch.
            start = column + "0"
            if len(result) < batch_size:
                break
    return sorted(
        list(results.items()), key=cmp_to_key(lambda x, y: cmp(x[1], y[1])), reverse=True
    )


def get_crashes_for_bucket(bucketid, limit=100, start=None):
    """
    Get limit crashes for the provided bucket, starting at start.

    We show the most recent crashes first, since they'll be the most
    relevant to the current state of the problem.
    """
    bucket_cf = pycassa.ColumnFamily(pool, "Bucket")
    try:
        if start:
            start = pycassa.util.uuid.UUID(start)
            return list(
                bucket_cf.get(
                    bucketid, column_start=start, column_count=limit, column_reversed=True
                ).keys()
            )[1:]
        else:
            return list(bucket_cf.get(bucketid, column_count=limit, column_reversed=True).keys())
    except NotFoundException:
        return []


def get_package_for_bucket(bucketid):
    """Returns the package and version for a given bucket."""

    bucket_cf = pycassa.ColumnFamily(pool, "Bucket")
    oops_cf = pycassa.ColumnFamily(pool, "OOPS")
    # Grab 5 OOPS IDs, just in case the first one doesn't have a Package field.
    try:
        oopsids = list(bucket_cf.get(bucketid, column_count=5).keys())
    except NotFoundException:
        return ("", "")
    for oopsid in oopsids:
        try:
            oops = oops_cf.get(str(oopsid), columns=["Package"])
            package_and_version = oops["Package"].split()[:2]
            if len(package_and_version) == 1:
                return (package_and_version[0], "")
            else:
                return package_and_version
        except (KeyError, NotFoundException):
            continue
    return ("", "")


def get_crash(oopsid, columns=None):
    oops_cf = pycassa.ColumnFamily(pool, "OOPS")
    try:
        oops = oops_cf.get(oopsid, columns=columns)
    except NotFoundException:
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
        indexes_cf = pycassa.ColumnFamily(pool, "Indexes")
        idx = "crash_signature_for_stacktrace_address_signature"
        bucket = indexes_cf.get(idx, [SAS])
        oops["SAS"] = bucket[SAS]
        return oops
    except NotFoundException:
        return oops
    return oops


def get_traceback_for_bucket(bucketid):
    oops_cf = pycassa.ColumnFamily(pool, "OOPS")
    # TODO fetching a crash ID twice, once here and once in get_stacktrace, is
    # a bit rubbish, but we'll write the stacktrace into the bucket at some
    # point and get rid of the contents of both of these functions.
    if len(get_crashes_for_bucket(bucketid, 1)) == 0:
        return None
    crash = str(get_crashes_for_bucket(bucketid, 1)[0])
    try:
        return oops_cf.get(crash, columns=["Traceback"])["Traceback"]
    except NotFoundException:
        return None


def get_stacktrace_for_bucket(bucketid):
    stacktrace_cf = pycassa.ColumnFamily(pool, "Stacktrace")
    oops_cf = pycassa.ColumnFamily(pool, "OOPS")
    # TODO: we should build some sort of index for this.
    SAS = "StacktraceAddressSignature"
    cols = ["Stacktrace", "ThreadStacktrace"]
    for crash in get_crashes_for_bucket(bucketid, 10):
        sas = None
        try:
            sas = oops_cf.get(str(crash), columns=[SAS])[SAS]
        except NotFoundException:
            pass
        if not sas:
            continue
        try:
            traces = stacktrace_cf.get(sas, columns=cols)
            return (traces.get("Stacktrace", None), traces.get("ThreadStacktrace", None))
        except NotFoundException:
            pass
    # We didn't have a stack trace for any of the signatures in this set of
    # crashes.
    # TODO in the future, we should go to the next 10 crashes.
    # fixing this would make a stacktrace appear for
    # https://errors.ubuntu.com/problem/24c9ba23fb469a953e7624b1dfb8fdae97c45618
    return (None, None)


def get_retracer_count(date):
    retracestats_cf = pycassa.ColumnFamily(pool, "RetraceStats")
    result = retracestats_cf.get(date)
    return _split_into_dictionaries(result)


def get_retracer_counts(start, finish):
    retracestats_cf = pycassa.ColumnFamily(pool, "RetraceStats")
    if finish == sys.maxsize:
        start = datetime.date.today() - datetime.timedelta(days=start)
        start = start.strftime("%Y%m%d")
        results = retracestats_cf.get_range()
        return (
            (date, _split_into_dictionaries(result)) for date, result in results if date < start
        )
    else:
        dates = _get_range_of_dates(start, finish)
        results = retracestats_cf.multiget(dates)
        return ((date, _split_into_dictionaries(results[date])) for date in results)


def get_retracer_means(start, finish):
    indexes_cf = pycassa.ColumnFamily(pool, "Indexes")
    start = datetime.date.today() - datetime.timedelta(days=start)
    start = start.strftime("%Y%m%d")
    finish = datetime.date.today() - datetime.timedelta(days=finish)
    finish = finish.strftime("%Y%m%d")

    # FIXME: We shouldn't be specifying a maximum number of columns
    timings = indexes_cf.get(
        "mean_retracing_time",
        column_start=start,
        column_finish=finish,
        column_count=1000,
        column_reversed=True,
    )
    to_float = pycassa.marshal.unpacker_for("FloatType")
    result = OrderedDict()
    for timing in timings:
        if not timing.endswith(":count"):
            branch = result
            parts = timing.split(":")
            # If you go far enough back, you'll hit the point before we
            # included the architecture in this CF, which will break here.
            # This is because there's a day that has some retracers for all
            # archs, and some for just i386.
            if len(parts) < 3:
                parts.append("all")
            end = parts[-1]
            for part in parts:
                if part is end:
                    branch[part] = to_float(timings[timing])
                else:
                    branch = branch.setdefault(part, {})
    return iter(result.items())


def get_crash_count(start, finish, release=None):
    counters_cf = pycassa.ColumnFamily(pool, "Counters")
    dates = _get_range_of_dates(start, finish)
    for date in dates:
        try:
            if release:
                key = "oopses:%s" % release
            else:
                key = "oopses"
            oopses = int(counters_cf.get(key, columns=[date])[date])
            yield (date, oopses)
        except NotFoundException:
            pass


def get_metadata_for_bucket(bucketid, release=None):
    bucketmetadata_cf = pycassa.ColumnFamily(pool, "BucketMetadata")
    try:
        if not release:
            return bucketmetadata_cf.get(bucketid, column_finish="~")
        else:
            ret = bucketmetadata_cf.get(bucketid)
            try:
                ret["FirstSeen"] = ret["~%s:FirstSeen" % release]
                ret["LastSeen"] = ret["~%s:LastSeen" % release]
            except KeyError:
                pass
            return ret
    except NotFoundException:
        return {}


def chunks(l, n):
    # http://stackoverflow.com/a/312464/190597
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


def get_metadata_for_buckets(bucketids, release=None):
    bucketmetadata_cf = pycassa.ColumnFamily(pool, "BucketMetadata")
    ret = OrderedDict()
    for buckets in chunks(bucketids, 5):
        if not release:
            ret.update(bucketmetadata_cf.multiget(buckets, column_finish="~"))
        else:
            ret.update(bucketmetadata_cf.multiget(buckets))
    if release:
        for bucket in ret:
            bucket = ret[bucket]
            try:
                bucket["FirstSeen"] = bucket["~%s:FirstSeen" % release]
                bucket["LastSeen"] = bucket["~%s:LastSeen" % release]
            except KeyError:
                # Rather than confuse developers with half release-specific
                # data. Of course this will only apply for the current row, so
                # it's possible subsequent rows will show release-specific
                # data.
                if "FirstSeen" in bucket:
                    del bucket["FirstSeen"]
                if "LastSeen" in bucket:
                    del bucket["LastSeen"]
    return ret


def get_user_crashes(user_token, limit=50, start=None):
    useroops_cf = pycassa.ColumnFamily(pool, "UserOOPS")
    results = {}
    try:
        if start:
            start = pycassa.util.uuid.UUID(start)
            result = useroops_cf.get(
                user_token, column_start=start, column_count=limit, include_timestamp=True
            )
        else:
            result = useroops_cf.get(user_token, column_count=limit, include_timestamp=True)
        for r in result:
            results[r] = {"submitted": result[r]}
        start = list(result.keys())[-1] + "0"
    except NotFoundException:
        return []
    return [
        (k[0], k[1])
        for k in sorted(iter(results.items()), key=operator.itemgetter(1), reverse=True)
    ]


def get_average_crashes(field, release, days=7):
    uniqueusers_cf = pycassa.ColumnFamily(pool, "UniqueUsers90Days")
    counters_cf = pycassa.ColumnFamily(pool, "Counters")
    dates = _get_range_of_dates(0, days)
    start = dates[-1]
    end = dates[0]
    try:
        key = "oopses:%s" % field
        g = counters_cf.xget(key, column_start=start, column_finish=end)
        oopses = pycassa.util.OrderedDict(x for x in g)
        g = uniqueusers_cf.xget(release, column_start=start, column_finish=end)
        users = pycassa.util.OrderedDict(x for x in g)
    except NotFoundException:
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
    uniqueusers_cf = pycassa.ColumnFamily(pool, "UniqueUsers90Days")
    daybucketscount_cf = pycassa.ColumnFamily(pool, "DayBucketsCount")
    # FIXME Why oh why did we do things this way around? It makes it impossible
    # to do a quick range scan. We should create DayBucketsCount2, replacing
    # this with a CF that's keyed on the bucket ID and has counter columns
    # named by the date.
    dates = _get_range_of_dates(0, days)
    start = dates[-1]
    end = dates[0]
    gen = uniqueusers_cf.xget(release, column_start=start, column_finish=end)
    users = dict(x for x in gen)
    for date in dates:
        try:
            count = daybucketscount_cf.get("%s:%s" % (release, date), columns=[bucketid])[bucketid]
        except NotFoundException:
            continue
        try:
            avg = float(count) / float(users[date])
        except (ZeroDivisionError, KeyError):
            continue
        t = int(time.mktime(time.strptime(date, "%Y%m%d")))
        yield ((t, avg))


def get_versions_for_bucket(bucketid):
    """Get the dictionary of (release, version) tuples for the given bucket
    with values of their instance counts. If the bucket does not exist,
    return an empty dict."""
    bv_count_cf = pycassa.ColumnFamily(pool, "BucketVersionsCount")
    try:
        return bv_count_cf.get(bucketid)
    except NotFoundException:
        return {}


def get_source_package_for_bucket(bucketid):
    oops_cf = pycassa.ColumnFamily(pool, "OOPS")
    bucket_cf = pycassa.ColumnFamily(pool, "Bucket")
    oopsids = list(bucket_cf.get(bucketid, column_count=10).keys())
    for oopsid in oopsids:
        try:
            oops = oops_cf.get(str(oopsid), columns=["SourcePackage"])
            return oops["SourcePackage"]
        except (KeyError, NotFoundException):
            continue
    return ""


def get_retrace_failure_for_bucket(bucketid):
    bucketretracefail_fam = pycassa.ColumnFamily(pool, "BucketRetraceFailureReason")
    try:
        failuredata = bucketretracefail_fam.get(bucketid)
        return failuredata
    except NotFoundException:
        return {}


def get_binary_packages_for_user(user):
    # query DayBucketsCount to ensure the package has crashes reported about
    # it rather than returning packages for which there will be no data.
    daybucketscount_cf = pycassa.ColumnFamily(pool, "DayBucketsCount")
    userbinpkgs_cf = pycassa.ColumnFamily(pool, "UserBinaryPackages")
    # if a package's last crash was reported more than a month ago then it
    # won't be returned here, however the package isn't likely to appear in
    # the most-common-problems.
    period = (datetime.date.today() - datetime.timedelta(30)).strftime("%Y%m")
    try:
        binary_packages = [pkg[0] + ":%s" % period for pkg in userbinpkgs_cf.xget(user)]
    except NotFoundException:
        return None
    if len(binary_packages) == 0:
        return None
    results = daybucketscount_cf.multiget_count(binary_packages, max_count=1)
    for result in results:
        if results[result] == 0:
            del results[result]
    return [k[0:-7] for k in list(results.keys())]


def get_package_crash_rate(
    release, src_package, old_version, new_version, pup, date, absolute_uri, exclude_proposed=False
):
    """Find the rate of Crashes, not other problems, about a package."""

    counters_cf = pycassa.ColumnFamily(pool, "Counters")
    proposed_counters_cf = pycassa.ColumnFamily(pool, "CountersForProposed")
    # the generic counter only includes Crashes for packages from official
    # Ubuntu sources and from systems not under auto testing
    old_vers_column = "%s:%s:%s" % (release, src_package, old_version)
    new_vers_column = "%s:%s:%s" % (release, src_package, new_version)
    results = {}
    try:
        # The first thing done is the reversing of the order that's why it
        # is column_start
        old_vers_data = counters_cf.get(
            old_vers_column, column_start=date, column_reversed=True, column_count=15
        )
    except NotFoundException:
        old_vers_data = None
    try:
        # this may be unnecessarily long since updates phase in ~3 days
        new_vers_data = counters_cf.get(new_vers_column, column_reversed=True, column_count=15)
    except NotFoundException:
        results["increase"] = False
        return results
    if exclude_proposed:
        try:
            # The first thing done is the reversing of the order that's why it
            # is column_start
            proposed_old_vers_data = proposed_counters_cf.get(
                old_vers_column, column_start=date, column_reversed=True, column_count=15
            )
        except NotFoundException:
            proposed_old_vers_data = None
        try:
            # this may be unnecessarily long since updates phase in ~3 days
            proposed_new_vers_data = proposed_counters_cf.get(
                new_vers_column, column_reversed=True, column_count=15
            )
        except NotFoundException:
            proposed_new_vers_data = None
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
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
    now = datetime.datetime.utcnow()
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


def get_package_new_buckets(src_pkg, previous_version, new_version):
    srcversionbuckets_cf = pycassa.ColumnFamily(pool, "SourceVersionBuckets")
    bucketversionsystems_cf = pycassa.ColumnFamily(pool, "BucketVersionSystems2")
    results = []
    # new version has no buckets
    try:
        n_data = [bucket[0] for bucket in srcversionbuckets_cf.xget((src_pkg, new_version))]
    except KeyError:
        return results
    # if previous version has no buckets return an empty list
    try:
        p_data = [bucket[0] for bucket in srcversionbuckets_cf.xget((src_pkg, previous_version))]
    except KeyError:
        p_data = []

    new_buckets = set(n_data).difference(set(p_data))
    for bucket in new_buckets:
        if isinstance(bucket, str):
            bucket = bucket.encode("utf-8")
        # do not return buckets that failed to retrace
        if bucket.startswith("failed:"):
            continue
        if isinstance(new_version, str):
            new_version = new_version.encode("utf-8")
        try:
            count = len(bucketversionsystems_cf.get((bucket, new_version), column_count=4))
        except NotFoundException:
            continue
        if count <= 2:
            continue
        results.append(bucket)
    return results


def record_bug_for_bucket(bucketid, bug):
    bucketmetadata_cf = pycassa.ColumnFamily(pool, "BucketMetadata")
    bugtocrashsignatures_cf = pycassa.ColumnFamily(pool, "BugToCrashSignatures")
    # We don't insert bugs into the database if we're using Launchpad staging,
    # as those will disappear in Launchpad but our copy would persist.
    if config.lp_use_staging == "False":
        bucketmetadata_cf.insert(bucketid, {"CreatedBug": bug})
        bugtocrashsignatures_cf.insert(int(bug), {bucketid: ""})


def get_signatures_for_bug(bug):
    try:
        bug = int(bug)
    except ValueError:
        return []

    bugtocrashsignatures_cf = pycassa.ColumnFamily(pool, "BugToCrashSignatures")
    try:
        gen = bugtocrashsignatures_cf.xget(bug)
        crashes = [crash for crash, unused in gen]
        return crashes
    except NotFoundException:
        return []


def bucket_exists(bucketid):
    bucket_cf = pycassa.ColumnFamily(pool, "Bucket")
    try:
        bucket_cf.get(bucketid, column_count=1)
        return True
    except NotFoundException:
        return False


def get_problem_for_hash(hashed):
    hashes_cf = pycassa.ColumnFamily(pool, "Hashes")
    try:
        return hashes_cf.get("bucket_%s" % hashed[0], columns=[hashed])[hashed]
    except NotFoundException:
        return None


def get_system_image_versions(image_type):
    images_cf = pycassa.ColumnFamily(pool, "SystemImages")
    try:
        versions = [version[0] for version in images_cf.xget(image_type)]
        return versions
    except NotFoundException:
        return None
