from cassandra.cqlengine import columns, models

DoesNotExist = models.Model.DoesNotExist


class ErrorTrackerTable(models.Model):
    __keyspace__ = "crashdb"
    __table_name_case_sensitive__ = True
    __abstract__ = True


class Indexes(ErrorTrackerTable):
    __table_name__ = "Indexes"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")

    def get_as_dict(*args, **kwargs) -> dict:
        query = Indexes.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result["column1"]] = result["value"]
        return d


class OOPS(ErrorTrackerTable):
    __table_name__ = "OOPS"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")

    def get_as_dict(*args, **kwargs) -> dict:
        query = OOPS.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result["column1"]] = result["value"]
        return d


class Stacktrace(ErrorTrackerTable):
    __table_name__ = "Stacktrace"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")


class RetraceStats(ErrorTrackerTable):
    __table_name__ = "RetraceStats"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Counter(db_field="value")


class Bucket(ErrorTrackerTable):
    __table_name__ = "Bucket"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.TimeUUID(db_field="column1", primary_key=True)
    value = columns.Blob(db_field="value")


class BucketRetraceFailureReason(ErrorTrackerTable):
    __table_name__ = "BucketRetraceFailureReason"
    key = columns.Blob(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")

    def get_as_dict(*args, **kwargs) -> dict:
        query = BucketRetraceFailureReason.objects.filter(*args, **kwargs)
        d = {}
        for result in query:
            d[result["column1"]] = result["value"]
        return d


class AwaitingRetrace(ErrorTrackerTable):
    __table_name__ = "AwaitingRetrace"
    key = columns.Text(db_field="key", primary_key=True)
    column1 = columns.Text(db_field="column1", primary_key=True)
    value = columns.Text(db_field="value")
