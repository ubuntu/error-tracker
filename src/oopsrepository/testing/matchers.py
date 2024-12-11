# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""Various oopsrepository specific matchers."""

import json
import time
import uuid
import os

import pycassa
from pycassa.cassandra.ttypes import NotFoundException
from testtools.matchers import Matcher, Mismatch

from oopsrepository import config


class HasOOPSSchema(Matcher):
    """Matches if a keyspace has a usable OOPS schema.

    This will write to the keyspace.
    """

    def match(self, keyspace):
        os.environ["OOPS_KEYSPACE"] = keyspace
        c = config.get_config()
        pool = pycassa.ConnectionPool(
            c["keyspace"], c["host"], username=c["username"], password=c["password"]
        )
        try:
            cf = pycassa.ColumnFamily(pool, "OOPS")
            cf.insert("key", {"date": json.dumps(time.time()), "URL": "a bit boring"})
            cf = pycassa.ColumnFamily(pool, "DayOOPS")
            cf.insert("20100212", {uuid.uuid1(): "key"})
            cf = pycassa.ColumnFamily(pool, "UserOOPS")
            cf.insert("user-token", {"key": ""})

            cf = pycassa.ColumnFamily(pool, "Bucket")
            cf.insert(
                "/bin/bash:11:x86_64:[vdso]+70c:...", {pycassa.util.uuid.uuid1(): ""}
            )
            cf = pycassa.ColumnFamily(pool, "DayBuckets")
            cf.insert(("20100212", "/bin/bash:11:x86_64:[vdso]+70c:..."), {"key": ""})
            cf = pycassa.ColumnFamily(pool, "DayBucketsCount")
            cf.add("20100212", "/bin/bash:11:x86_64:[vdso]+70c:...", 13)
        except NotFoundException as e:
            return Mismatch(e.why)
