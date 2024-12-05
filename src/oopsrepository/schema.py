# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""The schema for oopsrepository."""

from pycassa.types import (
    CompositeType,
    AsciiType,
    UTF8Type,
    CounterColumnType,
    IntegerType,
    DateType,
    )
from pycassa.system_manager import (
    SystemManager,
    TIME_UUID_TYPE,
    UTF8_TYPE,
    ASCII_TYPE,
    )

from . import config
from oopsrepository.cassandra_shim import workaround_1779

def create(config):
    """Create a schema.

    See DESIGN.txt for the schema description.

    :param config: The config (per oopsrepository.config.get_config) for
        oopsrepository.
    """
    keyspace = config['keyspace']
    creds = {'username': config['username'], 'password': config['password']}
    mgr = SystemManager(config['host'][0], credentials=creds)
    cfs = list(mgr.get_keyspace_column_families(keyspace).keys())
    try:
        if 'OOPS' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'OOPS',
                comparator_type=UTF8_TYPE, default_validation_class=UTF8_TYPE)
        if 'DayOOPS' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'DayOOPS',
                comparator_type=TIME_UUID_TYPE)
        if 'UserOOPS' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'UserOOPS',
                comparator_type=UTF8_TYPE)
        if 'SystemOOPSHashes' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace,
                'SystemOOPSHashes', comparator_type=UTF8_TYPE)
        if 'DayUsers' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'DayUsers',
                comparator_type=UTF8_TYPE)
        if 'Bucket' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'Bucket',
                comparator_type=TIME_UUID_TYPE, key_validation_class=UTF8_TYPE)
        # TODO It might be more performant to use just the date for the key and
        # a composite key of the bucket_id and the oops_id as the column name.
        composite = CompositeType(UTF8Type(), UTF8Type())
        if 'DayBuckets' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'DayBuckets',
                comparator_type=UTF8_TYPE, key_validation_class=composite)
        if 'DayBucketsCount' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'DayBucketsCount',
                comparator_type=UTF8_TYPE,
                default_validation_class=CounterColumnType())
        if 'BucketMetadata' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'BucketMetadata',
                comparator_type=UTF8_TYPE,
                default_validation_class=UTF8_TYPE)
        if 'BucketVersions' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'BucketVersions',
                comparator_type=UTF8_TYPE,
                default_validation_class=CounterColumnType())
        if 'BucketVersionsCount' not in cfs:
            composite = CompositeType(AsciiType(), AsciiType())
            workaround_1779(mgr.create_column_family,
                            keyspace,
                            'BucketVersionsCount',
                            key_validation_class=UTF8_TYPE,
                            comparator_type=composite,
                            default_validation_class=CounterColumnType())
        if 'BucketVersionsFull' not in cfs:
            composite = CompositeType(UTF8Type(), AsciiType(), AsciiType())
            workaround_1779(mgr.create_column_family,
                            keyspace,
                            'BucketVersionsFull',
                            key_validation_class=composite,
                            comparator_type=TIME_UUID_TYPE)
        if 'BucketVersionsDay' not in cfs:
            composite = CompositeType(UTF8Type(), AsciiType(), AsciiType())
            workaround_1779(mgr.create_column_family,
                            keyspace,
                            'BucketVersionsDay',
                            comparator_type=composite)
        if 'BucketVersionSystems2' not in cfs:
            composite = CompositeType(UTF8Type(), AsciiType())
            workaround_1779(mgr.create_column_family, keyspace,
                'BucketVersionSystems2', key_validation_class=composite,
                comparator_type=AsciiType())
        if 'BucketRetraceFailureReason' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace,
                'BucketRetraceFailureReason', comparator_type=UTF8_TYPE,
                default_validation_class=UTF8_TYPE)
        if 'Counters' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'Counters',
                comparator_type=UTF8_TYPE,
                default_validation_class=CounterColumnType())
        if 'CountersForProposed' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace,
                'CountersForProposed', comparator_type=UTF8_TYPE,
                default_validation_class=CounterColumnType())
        if 'FirstError' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'FirstError',
                            key_validation_class=ASCII_TYPE,
                            comparator_type=ASCII_TYPE,
                            default_validation_class=DateType())
        if 'ErrorsByRelease' not in cfs:
            composite = CompositeType(AsciiType(), DateType())
            workaround_1779(mgr.create_column_family, keyspace,
                            'ErrorsByRelease',
                            default_validation_class=DateType(),
                            key_validation_class=composite,
                            comparator_type=TIME_UUID_TYPE)
        if 'SourceVersionBuckets' not in cfs:
            composite = CompositeType(AsciiType(), AsciiType())
            workaround_1779(mgr.create_column_family, keyspace,
                'SourceVersionBuckets', key_validation_class=composite,
                 comparator_type=UTF8_TYPE)
        if 'Hashes' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace,
                            'Hashes', default_validation_class=UTF8_TYPE)
        if 'SystemsForErrorsByRelease' not in cfs:
            composite = CompositeType(AsciiType(), DateType())
            workaround_1779(mgr.create_column_family, keyspace,
                    'SystemsForErrorsByRelease',
                    key_validation_class=composite, comparator_type=UTF8_TYPE)
    finally:
        mgr.close()


if __name__ == '__main__':
    create(config.get_config())
