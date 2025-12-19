from cassandra.cqlengine import columns, models
from cassandra.marshal import float_unpack, varint_unpack

DoesNotExist = models.Model.DoesNotExist


class ErrorTrackerTable(models.Model):
    # __table_name_case_sensitive__ is deprecated already, but let's keep it in case we run on older machines.
    __table_name_case_sensitive__ = True
    __abstract__ = True


class Counters(ErrorTrackerTable):
    __table_name__ = "Counters"
    # the index we count
    #   - Ubuntu 24.04:zsh:5.9-6ubuntu2
    #   - Ubuntu 24.04:zsh
    key = columns.Blob(db_field="key", primary_key=True)
    # a datestamp
    #   - 20251101
    #   - 20240612
    column1 = columns.Text(db_field="column1", primary_key=True)
    # the count of crashes for that release:package[:version] that day
    value = columns.Counter(db_field="value")


class CountersForProposed(ErrorTrackerTable):
    __table_name__ = "CountersForProposed"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Counter(db_field="value")


class Indexes(ErrorTrackerTable):
    __table_name__ = "Indexes"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")

    @classmethod
    def get_as_dict(cls, *args, **kwargs) -> dict:
        query = cls.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            if result.key == b"mean_retracing_time" and not result.column1.endswith("count"):
                d[result.column1] = float_unpack(result.value)
            elif result.key == b"mean_retracing_time" and result.column1.endswith("count"):
                d[result.column1] = varint_unpack(result.value)
            else:
                d[result.column1] = result.value
        if not d:
            raise cls.DoesNotExist
        return d


class CouldNotBucket(ErrorTrackerTable):
    __table_name__ = "CouldNotBucket"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class DayOOPS(ErrorTrackerTable):
    __table_name__ = "DayOOPS"
    # a day
    #   - b'20160809'
    #   - b'20260116'
    key = columns.Blob(db_field="key", primary_key=True)
    # an OOPS that appeared that day
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    # an OOPS that appeared that day
    value = columns.Blob(db_field="value")
    # yes, both column1 and value are the same, just the format is changing


class DayUsers(ErrorTrackerTable):
    __table_name__ = "DayUsers"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class UserOOPS(ErrorTrackerTable):
    __table_name__ = "UserOOPS"
    # the user ID, aka machine-id
    #   - b'<just big long strings>'
    key = columns.Blob(db_field="key", primary_key=True)
    # an OOPS reported by that machine
    #   - <just random UUIDs>
    column1 = columns.Text(db_field="column1", primary_key=True)
    # appears to be unused
    value = columns.Blob(db_field="value")


class OOPS(ErrorTrackerTable):
    __table_name__ = "OOPS"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")

    @classmethod
    def get_as_dict(cls, *args, **kwargs) -> dict:
        query = cls.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result.column1] = result.value
        return d


class Stacktrace(ErrorTrackerTable):
    __table_name__ = "Stacktrace"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")


class SystemOOPSHashes(ErrorTrackerTable):
    __table_name__ = "SystemOOPSHashes"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class BucketMetadata(ErrorTrackerTable):
    __table_name__ = "BucketMetadata"
    # the bucket ID
    #   - b'/bin/zsh:11:makezleparams:execzlefunc:redrawhook:zlecore:zleread'
    key = columns.Blob(db_field="key", primary_key=True)
    # Which metadata
    #   - FirstSeen (package version)
    #   - LastSeen (package version)
    #   - FirstSeenRelease (Ubuntu series)
    #   - ~Ubuntu 25.04:LastSeen (package version)
    #   - CreatedBug
    column1 = columns.Text(db_field="column1", primary_key=True)
    # The corresponding value for the metadata
    #   - 5.9-6ubuntu2 (package version)
    #   - Ubuntu 18.04 (Ubuntu series)
    #   - <an LP bug number>
    value = columns.Text(db_field="value")

    @classmethod
    def get_as_dict(cls, *args, **kwargs) -> dict:
        query = cls.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result.column1] = result.value
        return d


class Hashes(ErrorTrackerTable):
    __table_name__ = "Hashes"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Blob(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")


class RetraceStats(ErrorTrackerTable):
    __table_name__ = "RetraceStats"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Counter(db_field="value")

    @classmethod
    def get_as_dict(cls, *args, **kwargs) -> dict:
        query = cls.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result.column1] = result.value
        return d


class Bucket(ErrorTrackerTable):
    __table_name__ = "Bucket"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class DayBuckets(ErrorTrackerTable):
    __table_name__ = "DayBuckets"
    # a day
    #   - 20160809
    #   - 20260116
    key = columns.Text(db_field="key", primary_key=True)
    # the bucketid:
    #   - /bin/zsh:11:__GI__IO_flush_all:_IO_cleanup:__run_exit_handlers:__GI_exit:zexit
    #   - /bin/brltty:*** buffer overflow detected ***: terminated
    key2 = columns.Text(db_field="key2", primary_key=True)
    # an OOPS id:
    #   - <uuid>
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class DayBucketsCount(ErrorTrackerTable):
    __table_name__ = "DayBucketsCount"
    # the index we count
    #   - 20251201
    #   - Ubuntu 24.04:20251201
    #   - zsh:amd64:20251201
    #   - Crash:zsh:amd64:20251201 (No idea about the difference with the previous example)
    #   - package:tvtime:(not installed)\nSetting up tvtime (1.0.11-8build2) ...\ndpkg: error processing package tvtime (--configure):\n installed tvtime package post-installation script subprocess returned error exit status 1\n
    key = columns.Blob(db_field="key", primary_key=True)
    # The bucketid we count:
    #   - /bin/zsh:11:__GI__IO_flush_all:_IO_cleanup:__run_exit_handlers:__GI_exit:zexit
    #   - /bin/brltty:*** buffer overflow detected ***: terminated
    column1 = columns.Text(db_field="column1", primary_key=True)
    # the counter itself
    value = columns.Counter(db_field="value")


class SourceVersionBuckets(ErrorTrackerTable):
    __table_name__ = "SourceVersionBuckets"
    key = columns.Ascii(db_field="key", primary_key=True)
    key2 = columns.Ascii(db_field="key2", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class BucketVersionSystems2(ErrorTrackerTable):
    __table_name__ = "BucketVersionSystems2"
    key = columns.Text(db_field="key", primary_key=True)
    key2 = columns.Ascii(db_field="key2", primary_key=True)
    column1 = columns.Ascii(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class BucketRetraceFailureReason(ErrorTrackerTable):
    __table_name__ = "BucketRetraceFailureReason"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")

    @classmethod
    def get_as_dict(cls, *args, **kwargs) -> dict:
        query = cls.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result.column1] = result.value
        return d


class AwaitingRetrace(ErrorTrackerTable):
    __table_name__ = "AwaitingRetrace"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")


class ErrorsByRelease(ErrorTrackerTable):
    __table_name__ = "ErrorsByRelease"
    # The release:
    #   - Ubuntu 25.04
    key = columns.Ascii(db_field="key", primary_key=True)
    # The datetime when we received the OOPS
    key2 = columns.DateTime(db_field="key2", primary_key=True)
    # The OOPS id
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    # The datetime when we received the OOPS (again???)
    value = columns.DateTime(db_field="value")


class BucketVersionsCount(ErrorTrackerTable):
    __table_name__ = "BucketVersionsCount"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.Ascii(db_field="column1", primary_key=True)
    column2 = columns.Ascii(db_field="column2", primary_key=True)
    value = columns.Counter(db_field="value")


class BugToCrashSignatures(ErrorTrackerTable):
    __table_name__ = "BugToCrashSignatures"
    # The bug number
    key = columns.VarInt(db_field="key", primary_key=True)
    # The crash signature:
    #   - /usr/lib/gnome-do/Do.exe:8:g_hash_table_lookup:mono_find_jit_icall_by_addr:mono_emit_jit_icall:mono_method_to_ir:mini_method_compile
    column1 = columns.Text(db_field="column1", primary_key=True)
    # appears to be usused
    value = columns.Blob(db_field="value")


class SystemImages(ErrorTrackerTable):
    # Very likely useless nowadays, doesn't have much up to date data
    __table_name__ = "SystemImages"
    # One of those:
    #   - device_image
    #   - rootfs_build
    #   - channel
    #   - device_name
    key = columns.Text(db_field="key", primary_key=True)
    # The version of the image type:
    #   - 16.04/community/walid/devel 101 titan
    #   - ubuntu-touch/vivid-proposed-customized-here 99 mako
    column1 = columns.Text(db_field="column1", primary_key=True)
    # Looks empty and unused
    value = columns.Blob(db_field="value")


class UniqueUsers90Days(ErrorTrackerTable):
    __table_name__ = "UniqueUsers90Days"
    # Ubuntu series ("Ubuntu 26.04", "Ubuntu 25.10", etc...)
    key = columns.Text(db_field="key", primary_key=True)
    # a datestamp ("20251101", "20240612", etc...)
    column1 = columns.Text(db_field="column1", primary_key=True)
    # the count of unique users of that release that day
    value = columns.BigInt(db_field="value")


class UserBinaryPackages(ErrorTrackerTable):
    __table_name__ = "UserBinaryPackages"
    # a team that usually owns packages (like for MIR)
    #   - debcrafters-packages
    #   - foundations-bugs
    #   - xubuntu-bugs
    key = columns.Ascii(db_field="key", primary_key=True)
    # package names
    #   - abiword
    #   - util-linux
    # looks to be binary packages only, but not 100% certain
    column1 = columns.Ascii(db_field="column1", primary_key=True)
    # looks unused
    value = columns.Blob(db_field="value")
