from cassandra.cqlengine import columns, models
from cassandra.marshal import float_unpack, varint_unpack

DoesNotExist = models.Model.DoesNotExist


class ErrorTrackerTable(models.Model):
    # __table_name_case_sensitive__ is deprecated already, but let's keep it in case we run on older machines.
    __table_name_case_sensitive__ = True
    __abstract__ = True


class Counters(ErrorTrackerTable):
    __table_name__ = "Counters"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
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
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class DayUsers(ErrorTrackerTable):
    __table_name__ = "DayUsers"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class UserOOPS(ErrorTrackerTable):
    __table_name__ = "UserOOPS"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
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
    key = columns.Text(db_field="key", primary_key=True)
    key2 = columns.Text(db_field="key2", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class DayBucketsCount(ErrorTrackerTable):
    __table_name__ = "DayBucketsCount"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
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
    key = columns.Ascii(db_field="key", primary_key=True)
    key2 = columns.DateTime(db_field="key2", primary_key=True)
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    value = columns.DateTime(db_field="value")


class BucketVersionsCount(ErrorTrackerTable):
    __table_name__ = "BucketVersionsCount"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.Ascii(db_field="column1", primary_key=True)
    column2 = columns.Ascii(db_field="column2", primary_key=True)
    value = columns.Counter(db_field="value")


class BugToCrashSignatures(ErrorTrackerTable):
    __table_name__ = "BugToCrashSignatures"
    key = columns.VarInt(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class SystemImages(ErrorTrackerTable):
    __table_name__ = "SystemImages"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class UniqueUsers90Days(ErrorTrackerTable):
    __table_name__ = "UniqueUsers90Days"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.BigInt(db_field="value")


class UserBinaryPackages(ErrorTrackerTable):
    __table_name__ = "UserBinaryPackages"
    key = columns.Ascii(db_field="key", primary_key=True)
    column1 = columns.Ascii(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")
