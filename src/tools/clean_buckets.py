#!/usr/bin/python3
# This script helps clean data with dangling cross-reference to old, already delete data.
# Namely, when we delete OOPSes from past years to lighten up the DB (using
# remove_old_data.py), this doesn't clean the Buckets pointing to those OOPSes.
# That's what this script is for. Ideally, we would have only one single script
# taking care of everything and keeping things consistent.

import sys

sys.path.insert(0, "../../src")

from errortracker import cassandra, cassandra_schema

cassandra.setup_cassandra()
session = cassandra.cassandra_session()


def clean_bucket(bucketid: str) -> bool:
    """
    Returns True if the Bucket is empty and is no longer relevant, False if it's
    still pointing to some relevant data.
    """
    try:
        for res in cassandra_schema.Bucket.objects.filter(key=bucketid).all():
            oops = str(res.column1)
            if cassandra_schema.OOPS.objects.filter(key=oops.encode()).count() == 0:
                # If an OOPS doesn't have any data at all, it's because it was
                # part of a series that has been cleaned. For the sake of
                # keeping the database size reasonable, let's also delete
                # references to that OOPS.
                print(f"OOPS {oops} has no data, deleting the Bucket entry")
                cassandra_schema.Bucket.objects.filter(key=bucketid, column1=oops).delete()
            else:
                return False
    except cassandra_schema.Bucket.DoesNotExist:
        print(f"{bucketid} does not exist, nothing to clean")
    return True


def clean_bucketretracefailurereason():
    dangling_buckets = cassandra_schema.BucketRetraceFailureReason.objects.distinct(["key"]).limit(
        None
    )
    total_count = 0
    cleaned_count = 0
    kept_buckets = []
    for bucket in dangling_buckets:
        total_count += 1
        bucket = bucket.key.decode()
        print(bucket)
        if clean_bucket(bucket):
            print("Cleaning BucketRetraceFailureReason")
            cassandra_schema.BucketRetraceFailureReason.objects.filter(
                key=bucket.encode()
            ).delete()
            cleaned_count += 1
        else:
            kept_buckets.append(bucket)
    print("Kept buckets:")
    print(kept_buckets)
    print(
        f"Went through {total_count} buckets in BucketRetraceFailureReason, cleaned {cleaned_count} and kept {len(kept_buckets)}"
    )


def clean_bucketmetadata():
    dangling_buckets = cassandra_schema.BucketMetadata.objects.distinct(["key"]).limit(None)
    total_count = 0
    cleaned_count = 0
    kept_buckets = []
    for bucket in dangling_buckets:
        total_count += 1
        bucket = bucket.key.decode()
        print(bucket)
        if clean_bucket(bucket):
            print("Cleaning BucketMetadata")
            cassandra_schema.BucketMetadata.objects.filter(key=bucket.encode()).delete()
            cleaned_count += 1
        else:
            kept_buckets.append(bucket)
    print("Kept buckets:")
    print(kept_buckets)
    print(
        f"Went through {total_count} buckets in BucketMetadata, cleaned {cleaned_count} and kept {len(kept_buckets)}"
    )


if __name__ == "__main__":
    clean_bucketretracefailurereason()
    clean_bucketmetadata()
