# oops-repository is Copyright 2011 Canonical Ltd.
#
# Canonical Ltd ("Canonical") distributes the oops-repository source code under
# the GNU Affero General Public License, version 3 ("AGPLv3"). See the file
# LICENSE in the source tree for more information.

"""Things to ease working with cassandra."""

from pycassa.cassandra.ttypes import InvalidRequestException

def workaround_1779(callable, *args, **kwargs):
    """Workaround cassandra not being able to do concurrent schema edits.

    The callable is tried until it does not raised InvalidRequestException
    with why = "Previous version mismatch. cannot apply."
    
    :param callable: The callable to call.
    :param args: The args for it.
    :param kwargs: The kwargs for it.
    :return: The result of calling the callable.
    """
    while True:
        # Workaround https://issues.apache.org/jira/browse/CASSANDRA-1779:
        # Cassandra cannot do concurrent schema changes.
        try:
            return callable(*args, **kwargs)
            break
        except InvalidRequestException as e:
            if e.why != 'Previous version mismatch. cannot apply.':
                raise
