#!/usr/bin/python

from __future__ import print_function
import apport
import sys
import pycassa
from pycassa.cassandra.ttypes import NotFoundException
from daisy.utils import split_package_and_version
from daisy import config
from daisy.metrics import VerboseListener
from collections import defaultdict
import argparse
import uuid
import time

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=60,
                              listeners=[VerboseListener()],
                              pool_size=15, max_retries=20, credentials=creds)

oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
indexes_cf = pycassa.ColumnFamily(pool, 'Indexes')
awaiting_retrace_cf = pycassa.ColumnFamily(pool, 'AwaitingRetrace')
bv_full_cf = None
bv_day_cf = None
write_oops_cf = None

counts = defaultdict(int)

wait_amount = 30000000
wait = wait_amount

idx_key = 'crash_signature_for_stacktrace_address_signature'
crash_sigs = {k:v for k,v in indexes_cf.xget(idx_key)}

start = pycassa.columnfamily.gm_timestamp()

# We don't need Stacktrace or ThreadStacktrace or any of that because we get
# the crash signature from *just* the SAS for binary crashes.
columns = ['ExecutablePath', 'Traceback', 'ProblemType', 'DuplicateSignature',
           'StacktraceAddressSignature', 'DistroRelease', 'Package',
           'InterpreterPath', 'OopsText', 'Signal', 'AssertionMessage',
           'Stacktrace', 'StacktraceTop', 'ProcMaps']
columns.sort()

kwargs = {
    'include_timestamp': True,
    'buffer_size': (1024*2),
    'columns': columns,
}

def print_totals(force=False):
    global wait
    if force:
        print('Final total:')
    if force or (pycassa.columnfamily.gm_timestamp() - start > wait):
        wait += wait_amount
        t = float(counts['binary'] + counts['python'] + counts['dups'] +
                  counts['no_sas'] + counts['no_signature'])
        r = (t / (pycassa.columnfamily.gm_timestamp() - start) * 1000000 * 60)
        print('Processed:', t, '(%d/min)' % r, sep='\t')
        for k in counts:
            print('%s:' % k, counts[k], sep='\t\t')
        print
        sys.stdout.flush()

def update_bucketversions(bucketid, oops, key):
    global bv_full_cf
    global bv_day_cf

    if 'ProblemType' not in oops:
        return

    key = uuid.UUID(key)
    version = ''
    package = oops.get('Package', '')
    release = oops.get('DistroRelease', '')
    # These are tuples of (value, timestamp)
    if release:
        release = release[0].encode('ascii', errors='ignore')
    if package:
        package = package[0].encode('ascii', errors='ignore')
        package, version = split_package_and_version(package)

    if not package:
        counts['no_package'] += 1
    if not release:
        counts['no_release'] += 1

    if bv_full_cf:
        try:
            bv_full_cf.insert((bucketid, release, version), {key: ''})
        except:
            print(repr(bucketid), type(bucketid))
            print(repr(release), type(release))
            print(repr(version), type(version))
            print(repr(key), type(key))
            raise

    # Unlike the code in oops-repository, we use the day of the OOPS, so we
    # don't end up with one very wide row for when we ran this. We'll do a
    # repair on everything up to the current day after this is run.
    if bv_day_cf:
        ts = oops['ProblemType'][1]
        day_key = time.strftime('%Y%m%d', time.gmtime(ts / 1000000))
        try:
            bv_day_cf.insert(day_key, {(bucketid, release, version): ''})
        except:
            print(repr(bucketid), type(bucketid))
            print(repr(release), type(release))
            print(repr(version), type(version))
            print(repr(key), type(key))
            raise

def handle_duplicate_signature(key, o):
    ds = o['DuplicateSignature'][0]
    ds = ds[:32768]
    ds = ds.encode('utf-8')
    update_bucketversions(ds, o, key)
    counts['dups'] += 1

def handle_binary(key, o):
    addr_sig = o['StacktraceAddressSignature'][0]
    if not addr_sig:
        counts['empty_sas'] += 1
        return

    crash_sig = crash_sigs.get(addr_sig, None)

    if crash_sig:
        crash_sig = crash_sig[:32768]
        update_bucketversions(crash_sig, o, key)
        counts['binary'] += 1
    else:
        # If we cannot find the address signature, it may have been bucketed
        # while this program was running. We do not need to look up the address
        # signature in the actual indexes CF though, as the new daisy code
        # would have already written this to bucketversions.
        counts['no_signature'] += 1
        #count_retracing(addr_sig, key, o)

def count_retracing(addr_sig, key, o):
    try:
        indexes_cf.get('retracing', [addr_sig])
        counts['retracing'] += 1
    except NotFoundException:
        counts['not_retracing'] += 1
        try:
            awaiting_retrace_cf.get(addr_sig, [key])
            counts['awaiting_retrace'] += 1
        except NotFoundException:
            counts['not_awaiting_retrace'] += 1

def repair_sas(key, o, report):
    '''Back at the January sprint, Martin found and fixed a bug that was
    preventing the SAS from being generated. There are at least 796,000 reports
    in the database that are missing one. Repair them, if possible.'''

    sas = None
    try:
        sas = report.crash_signature_addresses()
    except:
        import traceback
        print('Could not generate crash_signature_addresses for:', key)
        traceback.print_exc()

    if not sas:
        counts['could_not_repair_sas'] += 1
        return False

    if write_oops_cf:
        write_oops_cf.insert(key, {'StacktraceAddressSignature': sas})
    o['StacktraceAddressSignature'] = sas
    return True

def main():
    for key, o in oops_cf.get_range(**kwargs):
        print_totals()

        if 'DuplicateSignature' in o:
            handle_duplicate_signature(key, o)
            continue

        report = apport.Report()
        for k in o:
            report[k.encode('utf-8')] = o[k][0].encode('utf-8')
        crash_signature = report.crash_signature()
        if crash_signature:
            crash_signature = crash_signature[:32768]
            if 'Traceback' in o:
                counts['python'] += 1
            elif 'OopsText' in o:
                counts['kernel_oops'] += 1
            update_bucketversions(crash_signature, o, key)
        elif 'StacktraceTop' in o and 'Signal' in o:
            if 'StacktraceAddressSignature' not in o:
                counts['no_sas'] += 1
                if not repair_sas(key, o, report):
                    continue
            handle_binary(key, o)
        else:
            if 'Signal' in o:
                # We don't have a stacktrace for this signal failure.
                sig = o['Signal'][0]
                counts['sig%s' % sig] += 1
            if 'Traceback' in o:
                # We don't have a long enough Traceback to form a signature.
                # These should be replaced with a better signature function
                # that works with short tracebacks.
                counts['poor_tb'] += 1
            counts['unknown'] += 1

    print_totals(force=True)

def parse_options():
    parser = argparse.ArgumentParser(description='Rebuild BucketVersions.')
    parser.add_argument('--write-hosts', nargs='+',
                        help='Cassandra host and IP (colon-separated) to write'
                        ' results to.')
    return parser.parse_args()

if __name__ == '__main__':
    options = parse_options()
    if options.write_hosts:
        write_pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                                            options.write_hosts, timeout=60,
                                            pool_size=15, max_retries=100,
                                            credentials=creds)
        bv_full_cf = pycassa.ColumnFamily(write_pool, 'BucketVersionsFull')
        bv_day_cf = pycassa.ColumnFamily(write_pool, 'BucketVersionsDay')
        write_oops_cf = pycassa.ColumnFamily(write_pool, 'OOPS')

    main()
