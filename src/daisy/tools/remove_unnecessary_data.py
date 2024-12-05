#!/usr/bin/python

from __future__ import print_function
import pycassa
import sys

from daisy import config
from pycassa.cassandra.ttypes import NotFoundException, InvalidRequestException

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              max_retries=100, credentials=creds)

oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
indexes_cf = pycassa.ColumnFamily(pool, 'Indexes')
awaiting_retrace_cf = pycassa.ColumnFamily(pool, 'AwaitingRetrace')

never_needed_columns = ['Stacktrace', 'ThreadStacktrace']
unneeded_columns = ['Disassembly', 'ProcMaps', 'ProcStatus',
                    'Registers', 'StacktraceTop']
counts = 0
ire_count = 0

wait_amount = 30000000
wait = wait_amount
start = pycassa.columnfamily.gm_timestamp()


def print_totals(force=False):
    global wait
    if force or (pycassa.columnfamily.gm_timestamp() - start > wait):
        wait += wait_amount
        r = (float(counts) / (pycassa.columnfamily.gm_timestamp() - start)
             * 1000000 * 60)
        print('Processed:', counts, '(%d/min)' % r, sep='\t')
        print
        sys.stdout.flush()

for oops in oops_cf.get_range(start='f852276e-8456-11e3-913e-e4115b0f8a4a',
        columns=['StacktraceAddressSignature','DistroRelease'],
        buffer_size=2*1024):
    eol = False
    oops_id = oops[0]
    data = oops[1]
    signature = data.get('StacktraceAddressSignature', '')
    release = data.get('DistroRelease', '')
    print_totals()
    counts += 1
    # remove Stacktrace and ThreadStacktrace from everything
    oops_cf.remove(oops_id, columns=never_needed_columns)
    # for EoL releases remove the columns
    if release in ['Ubuntu 13.04']:
        eol = True
        print('Removing data for EoL %s' % oops_id)
        oops_cf.remove(oops_id, columns=unneeded_columns)
    if not signature:
        print("%s has no signature" % oops_id)
        continue
    # if it failed it can't be awaiting retracing
    if signature.startswith('failed:'):
        print("%s failed to retrace" % oops_id)
        continue
    try:
        awaiting = awaiting_retrace_cf.get(signature)
        print("%s is waiting to retrace" % oops_id)
        # we don't want to retrace EoL releases
        if eol:
            print("Removing retrace of %s" % oops_id)
            awaiting_retrace_cf.remove(signature)
        continue
    except NotFoundException:
        pass
    except InvalidRequestException:
        ire_count +=1
        print('Long signature count: %s' % ire_count)
        continue
    try:
        idx = 'retracing'
        crash_signature = indexes_cf.get(idx, [signature])
        print("%s is retracing" % oops_id)
        continue
    except NotFoundException:
        pass
    print('Removing data for %s' % oops_id)
    #if counts >= 10:
    #    break
    oops_cf.remove(oops_id, columns=unneeded_columns)
print_totals(force=True)
