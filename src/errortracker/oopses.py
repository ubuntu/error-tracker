# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""basic operations on oopses in the db."""

import json
import locale
import re
import time
import uuid
from datetime import datetime
from hashlib import md5, sha1

from cassandra.cqlengine.query import BatchQuery

from errortracker import cassandra_schema
from errortracker.cassandra import cassandra_session

DAY = 60 * 60 * 24
MONTH = DAY * 30

_cassandra_session = None


def prune():
    """Remove OOPSES that are over 30 days old."""
    # Find days to prune
    days = set()
    prune_to = time.strftime("%Y%m%d", time.gmtime(time.time() - MONTH))
    for dayoops in cassandra_schema.DayOOPS.objects.distinct(["key"]):
        key = dayoops.key.decode()
        if key < prune_to:
            days.add(key)
    if not days:
        return
    # collect all the oopses (buffers all in memory; may want to make
    # incremental in future)
    for day in days:
        oops_ids = list(
            set(
                dayoops.value
                for dayoops in cassandra_schema.DayOOPS.filter(key=day.encode()).only(["value"])
            )
        )
        with BatchQuery() as b:
            cassandra_schema.DayOOPS.objects.batch(b).filter(key=day.encode()).delete()
            for id in oops_ids:
                cassandra_schema.OOPS.objects.batch(b).filter(key=id).delete()


def insert(oopsid, oops_json, user_token=None, fields=None, proposed_pkg=False) -> str:
    """Insert an OOPS into the system.

    :return: The day which the oops was filed under.
    """
    # make sure the oops report is a json dict, and break out each key to a
    # separate column. For now, rather than worrying about typed column values
    # we just coerce them all to strings.
    oops_dict = json.loads(oops_json)
    assert isinstance(oops_dict, dict)
    insert_dict = {}
    for key, value in list(oops_dict.items()):
        insert_dict[key] = str(value)
    return _insert(oopsid, insert_dict, user_token, fields, proposed_pkg)


def insert_dict(
    oopsid,
    oops_dict,
    user_token=None,
    fields=None,
    proposed_pkg=False,
    ttl=None,
) -> str:
    """Insert an OOPS into the system.

    :return: The day which the oops was filed under.
    """
    assert isinstance(oops_dict, dict)
    return _insert(oopsid, oops_dict, user_token, fields, proposed_pkg, ttl)


def _insert(
    oopsid,
    insert_dict,
    user_token=None,
    fields=None,
    proposed_pkg=False,
    ttl=None,
) -> str:
    """Internal function. Do not call this directly.

    :param oopsid: The identifier for this OOPS.
    :param insert_dict: A dictionary containing the data to associate this OOPS
        with.
    :param user_token: An identifier for the user who experienced this OOPS.
    :param fields: A dictionary containing keys to increment counters for.
    :param proposed_pkg: True if the report's Tags contain package-from-proposed
    :param ttl: boolean for setting the time to live for the column
    :return: The day which the oops was filed under.
    """
    try:
        # Make sure the datetime will get formatted "correctly" in that cursed time format: Mon May  5 14:46:10 2025
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
        # Try to get the actual day of that crash, otherwise fallback to today
        crash_datetime = datetime.strptime(insert_dict["Date"], "%c")
        day_key = crash_datetime.strftime("%Y%m%d")
    except Exception:
        crash_datetime = datetime.now()
        day_key = datetime.strftime(datetime.now(), "%Y%m%d")
    now_uuid = uuid.uuid1()

    if ttl:
        ttl = 2592000

    for key, value in list(insert_dict.items()):
        # try to avoid an OOPS re column1 being missing
        if not key:
            continue
        cassandra_schema.OOPS.create(key=oopsid.encode(), column1=key, value=value).ttl(ttl)

    automated_testing = False
    if user_token and user_token.startswith("deadbeef"):
        automated_testing = True

    cassandra_schema.DayOOPS.create(key=day_key.encode(), column1=now_uuid, value=oopsid.encode())
    if "DistroRelease" in insert_dict:
        cassandra_schema.ErrorsByRelease.create(
            key=insert_dict["DistroRelease"],
            key2=datetime.now(),
            column1=now_uuid,
            value=crash_datetime,
        )

    # Systems running automated tests should not be included in the OOPS count.
    if not automated_testing:
        # Provide quick lookups of the total number of oopses for the day by
        # maintaining a counter.
        cassandra_schema.Counters.filter(key=b"oopses", column1=day_key).update(value=1)
        if fields:
            for field in fields:
                field = field.encode("ascii", errors="replace").decode()
                cassandra_schema.Counters.filter(
                    key=f"oopses:{field}".encode(), column1=day_key
                ).update(value=1)
        if proposed_pkg:
            for field in fields:
                field = field.encode("ascii", errors="replace").decode()
                cassandra_schema.CountersForProposed.filter(
                    key=f"oopses:{field}".encode(), column1=day_key
                ).update(value=1)

    if user_token:
        cassandra_schema.UserOOPS.create(key=user_token.encode(), column1=oopsid, value=b"")
        # Build a unique identifier for crash reports to prevent the same
        # crash from being reported multiple times.
        date = insert_dict.get("Date", "")
        exec_path = insert_dict.get("ExecutablePath", "")
        proc_status = insert_dict.get("ProcStatus", "")
        if date and exec_path and proc_status:
            crash_id = f"{date}:{exec_path}:{proc_status}"
            crash_id = md5(crash_id.encode()).hexdigest()
            cassandra_schema.SystemOOPSHashes.create(
                key=user_token.encode(), column1=crash_id, value=b""
            )
        # TODO we can drop this once we're successfully using ErrorsByRelease.
        # We'll have to first ensure that all the calculated historical data is
        # in UniqueUsers90Days.
        cassandra_schema.DayUsers.create(key=day_key.encode(), column1=user_token, value=b"")
        if fields:
            for field in fields:
                field = field.encode("ascii", errors="replace").decode()
                field_day = f"{field}:{day_key}"
                cassandra_schema.DayUsers.create(
                    key=field_day.encode(), column1=user_token, value=b""
                )

    return day_key


def bucket(oopsid, bucketid, fields=None, proposed_fields=False):
    """Adds an OOPS to a bucket, a collection of OOPSes that form a single
    issue. If the bucket does not exist, it will be created.

    :return: The day which the bucket was filed under.
    """
    session = cassandra_session()
    # Get the timestamp.
    try:
        results = session.execute(
            session.prepare(
                f'SELECT WRITETIME (value) FROM {session.keyspace}."OOPS" WHERE key = ? LIMIT 1'
            ),
            [oopsid.encode()],
        )
        timestamp = list(results)[0]["writetime(value)"]
        day_key = time.strftime("%Y%m%d", time.gmtime(timestamp / 1000000))
    except IndexError:
        # Eventual consistency. This OOPS probably occurred today.
        day_key = time.strftime("%Y%m%d", time.gmtime())

    cassandra_schema.Bucket.create(key=bucketid, column1=uuid.UUID(oopsid), value=b"")
    cassandra_schema.DayBuckets.create(key=day_key, key2=bucketid, column1=oopsid, value=b"")

    if fields is not None:
        resolutions = (day_key[:4], day_key[:6], day_key)
        # All buckets for the given resolution.
        for field in fields:
            for resolution in resolutions:
                # We have no way of knowing whether an increment has been
                # performed if the write fails unexpectedly (CASSANDRA-2495).
                # We will apply eventual consistency to this problem and
                # tolerate slightly inaccurate counts for the span of a single
                # day, cleaning up once this period has passed. This will be
                # done by counting the number of columns in DayBuckets for the
                # day and bucket ID.
                field_resolution = ":".join((field, resolution))
                cassandra_schema.DayBucketsCount(
                    key=field_resolution.encode(), column1=bucketid
                ).update(value=1)
        for resolution in resolutions:
            cassandra_schema.DayBucketsCount(key=resolution.encode(), column1=bucketid).update(
                value=1
            )
    return day_key


def update_bucket_versions_count(crash_signature: str, release: str, version: str):
    cassandra_schema.BucketVersionsCount(
        key=crash_signature, column1=release, column2=version
    ).update(value=1)


def update_bucket_metadata(bucketid, source, version, comparator, release=""):
    # We only update the first and last seen version fields. We do not update
    # the current version field as talking to Launchpad is an expensive
    # operation, and we can do that out of band.
    metadata = {}
    release_re = re.compile(r"^Ubuntu \d\d.\d\d$")

    bucketmetadata = cassandra_schema.BucketMetadata.get_as_dict(key=bucketid.encode())
    # TODO: Drop the FirstSeen and LastSeen fields once BucketVersionsCount
    # is deployed, since we can just do a get(column_count=1) for the first
    # seen version and get(column_reversed=True, column_count=1) for the
    # last seen version.
    # N.B.: This presumes that we are using the DpkgComparator which we
    # won't be when we move to DSE.
    firstseen = bucketmetadata.get("FirstSeen", None)
    if firstseen and comparator(firstseen, version) < 0:
        metadata["FirstSeen"] = firstseen
    else:
        metadata["FirstSeen"] = version
    firstseen_release = bucketmetadata.get("FirstSeenRelease", None)
    # Some funny releases were already written to FirstSeenRelease,
    # see LP: #1805912, ensure they are overwritten.
    if firstseen_release and not release_re.match(firstseen_release):
        firstseen_release = None
    if not firstseen_release or (release.split()[-1] < firstseen_release.split()[-1]):
        metadata["FirstSeenRelease"] = release
    lastseen = bucketmetadata.get("LastSeen", None)
    if lastseen and comparator(lastseen, version) > 0:
        metadata["LastSeen"] = lastseen
    else:
        metadata["LastSeen"] = version
    lastseen_release = bucketmetadata.get("LastSeenRelease", None)
    # Some funny releases were already written to LastSeenRelease,
    # see LP: #1805912, ensure they are overwritten.
    if lastseen_release and not release_re.match(lastseen_release):
        lastseen_release = None
    if not lastseen_release or (lastseen_release.split()[-1] < release.split()[-1]):
        metadata["LastSeenRelease"] = release

    if release:
        k = "~%s:FirstSeen" % release
        firstseen = bucketmetadata.get(k, None)
        if firstseen and comparator(firstseen, version) < 0:
            metadata[k] = firstseen
        else:
            metadata[k] = version
        k = "~%s:LastSeen" % release
        lastseen = bucketmetadata.get(k, None)
        if lastseen and comparator(lastseen, version) > 0:
            metadata[k] = lastseen
        else:
            metadata[k] = version

    if metadata:
        metadata["Source"] = source
        for k, v in metadata.items():
            cassandra_schema.BucketMetadata.create(key=bucketid.encode(), column1=k, value=v)


def update_bucket_systems(bucketid, system, version=None):
    """Keep track of the unique systems in a bucket with a specific version of
    software."""
    if not system or not version:
        return
    if not version:
        return
    cassandra_schema.BucketVersionSystems2.create(
        key=bucketid, key2=version, column1=system, value=b""
    )


def update_source_version_buckets(source, version, bucketid):
    # according to debian policy neither the package or version should have
    # utf8 in it but either some archives do not know that or something is
    # wonky with apport
    source = source.encode("ascii", errors="replace").decode()
    version = version.encode("ascii", errors="replace").decode()
    cassandra_schema.SourceVersionBuckets.create(
        key=source, key2=version, column1=bucketid, value=b""
    )


def update_bucket_hashes(bucketid):
    """Keep a mapping of SHA1 hashes to the buckets they represent.
    These hashes will be used for shorter bucket URLs."""
    bucket_sha1 = sha1(bucketid.encode()).hexdigest()
    k = "bucket_%s" % bucket_sha1[0]
    cassandra_schema.Hashes.create(key=k.encode(), column1=bucket_sha1.encode(), value=bucketid)
