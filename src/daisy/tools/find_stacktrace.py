#!/usr/bin/python
import sys

from urllib import quote

import pycassa
from pycassa.cassandra.ttypes import NotFoundException

from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=1,
                              pool_size=6, credentials=creds)
oops = pycassa.ColumnFamily(pool, 'OOPS')
bucket = pycassa.ColumnFamily(pool, 'Bucket')
hashes = pycassa.ColumnFamily(pool, 'Hashes')
stack = pycassa.ColumnFamily(pool, 'Stacktrace')
indexes = pycassa.ColumnFamily(pool, 'Indexes')
awaiting_retrace = pycassa.ColumnFamily(pool, 'AwaitingRetrace')


def main(hashed):
    # TODO this does not work for OOPS's with a traceback or
    # duplicatesignature
    try:
        oops_details = oops.get(hashed, ['StacktraceAddressSignature'])
    except NotFoundException:
        print("OOPS instance %s not found" % hashed)
        sys.exit(1)
    signature = oops_details['StacktraceAddressSignature']
    print("SAS: %s" % signature)
    print_stacktrace(signature)


def oops_information(oops_id):
    try:
        oops_details = oops.get(oops_id, ['Date'])
    except NotFoundException:
        print("OOPS instance %s not found" % oops_id)
        return ''
    date = oops_details['Date']
    return date


def print_stacktrace(signature):
    try:
        idx = 'crash_signature_for_stacktrace_address_signature'
        crash_sig = indexes.get(idx, [signature])
        print("Found crash signature for SAS: %s" %
              crash_sig[signature])
        print("https://errors.ubuntu.com/bucket/?id=%s" %
              quote(crash_sig[signature]))
    except NotFoundException:
        pass
    try:
        awaiting = awaiting_retrace.get(signature)
        print("Waiting to retrace SAS")
        print("%i items are awaiting retrace." % len(awaiting))
        for a in awaiting:
            date = oops_information(a)
            print("https://errors.ubuntu.com/oops/%s - %s" % (a, date))
    except NotFoundException:
        pass
    try:
        idx = 'retracing'
        crash_signature = indexes.get(idx, [signature])
        print("Retracing SAS")
    except NotFoundException:
        pass
    try:
        print("%s:\n%s" % (signature, stack.get(signature)))
    except NotFoundException:
        pass

if __name__ == '__main__':
    hashed = sys.argv[1]
    main(hashed)
