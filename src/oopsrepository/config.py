# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""The config for oopsrepository."""

import os


def get_config():
    """Get a dict of the config variables controlling oopsrepository."""
    result = dict(
        keyspace=os.environ.get("OOPS_KEYSPACE"),
        host=[os.environ.get("OOPS_HOST", "localhost")],
        username=os.environ.get("OOPS_USERNAME", ""),
        password=os.environ.get("OOPS_PASSWORD", ""),
    )
    if not result["keyspace"]:
        raise Exception("No keyspace set - set via OOPS_KEYSPACE")
    return result
