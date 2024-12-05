#!/usr/bin/python
# -*- coding: utf-8 -*-
# 
# Copyright © 2011-2013 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation; version 3 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero Public License for more details.
# 
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pycassa.types import (
    DateType,
    )

from pycassa.system_manager import (
    SystemManager,
    UTF8_TYPE,
    LONG_TYPE,
    ASCII_TYPE,
    INT_TYPE,
    TIME_UUID_TYPE,
    FLOAT_TYPE,
    )

from daisy import config
from oopsrepository.cassandra_shim import workaround_1779
from pycassa.types import CounterColumnType

def create():
    keyspace = config.cassandra_keyspace
    creds = {'username': config.cassandra_username,
             'password': config.cassandra_password}
    mgr = SystemManager(config.cassandra_hosts[0], credentials=creds)
    cfs = mgr.get_keyspace_column_families(keyspace).keys()
    try:
        if 'Indexes' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'Indexes',
                comparator_type=UTF8_TYPE)
        if 'Stacktrace' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'Stacktrace',
                comparator_type=UTF8_TYPE,
                default_validation_class=UTF8_TYPE)
        if 'AwaitingRetrace' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'AwaitingRetrace',
                key_validation_class=UTF8_TYPE,
                comparator_type=UTF8_TYPE,
                default_validation_class=UTF8_TYPE)
        if 'RetraceStats' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'RetraceStats',
                comparator_type=UTF8_TYPE,
                default_validation_class=CounterColumnType())
        if 'UniqueUsers90Days' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'UniqueUsers90Days',
                comparator_type=UTF8_TYPE,
                key_validation_class=UTF8_TYPE,
                default_validation_class=LONG_TYPE)
        if 'BadRequest' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'BadRequest',
                default_validation_class=CounterColumnType())
        if 'UserBinaryPackages' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'UserBinaryPackages',
                # The key_validation_class is a launchpad team ID, which is
                # always ascii.
                # The comparator is a binary package name, which is always
                # ascii according to Debian policy.
                # default_validation_class is bytes as it's always NULL.
                key_validation_class=ASCII_TYPE,
                comparator_type=ASCII_TYPE)
        if 'BugToCrashSignatures' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'BugToCrashSignatures',
                key_validation_class=INT_TYPE,
                comparator_type=UTF8_TYPE)
        if 'CouldNotBucket' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'CouldNotBucket',
                comparator_type=TIME_UUID_TYPE)
        if 'TimeToRetrace' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'TimeToRetrace',
                default_validation_class=FLOAT_TYPE)
        if 'UniqueSystemsForErrorsByRelease' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace,
                            'UniqueSystemsForErrorsByRelease',
                            comparator_type=DateType(),
                            default_validation_class=LONG_TYPE)
        if 'SystemImages' not in cfs:
            workaround_1779(mgr.create_column_family, keyspace, 'SystemImages',
                key_validation_class=UTF8_TYPE,
                comparator_type=UTF8_TYPE)
    finally:
        mgr.close()

if __name__ == '__main__':
    create()
