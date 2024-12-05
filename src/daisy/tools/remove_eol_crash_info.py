#!/usr/bin/python

# Review crashes in the OOPS table for any from an End of Life release and
# remove unneeded_columns from those OOPSes.

from __future__ import print_function
import pycassa
import sys
import time

from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              max_retries=100, credentials=creds)

#auth_provider = PlainTextAuthProvider(
#    username=config['username'], password=config['password'])
#cluster = Cluster(config['host'], auth_provider=auth_provider)
#cassandra_session = cluster.connect(config['keyspace'])
#cassandra_session.default_consistency_level = ConsistencyLevel.ONE

oops_cf = pycassa.ColumnFamily(pool, 'OOPS')

never_needed_columns = ('Stacktrace', 'ThreadStacktrace')
unneeded_columns = ('Disassembly', 'ProcMaps', 'ProcStatus',
                    'Registers', 'StacktraceTop', 'Lsusb',
                    'CrashReports', 'HookError_source_nautilus',
                    'HookError_source_totem', 'RelatedPackageVersions',
                    'HotSpotError', 'CrashDB',
                    'DpkgHistoryLog.txt', 'DpkgTerminalLog.txt',
                    'Dependencies', 'UserGroups', 'UpgradeStatus')
# 2019-07-17
#   Dependencies is long and doesn't seem useful
#   UserGroups doesn't seem useful either
#   UpgradeStatus can be wrong anyway

#   ProcCpuinfoMinimal
#   UnreportableReason
#   HookError.* (its off the source package though so ones with lots of
#   crashes e.g. HookError_source_totem)
#   https://errors.ubuntu.com/oops/c9c29f02-30f9-11e7-ad57-fa163e54c21f
#       whole bunch of dmi, xserver, xorg stuff

counts = 0

wait_amount = 30000000
wait = wait_amount
start = time.time() * 1000000

def print_totals(force=False):
    global wait
    #if force or (pycassa.columnfamily.gm_timestamp() - start > wait):
    now = time.time() * 1000000
    if force or (now - start > wait):
        wait += wait_amount
        r = (float(counts) / (now - start)
             * 1000000 * 60)
        print('Processed:', counts, '(%d/min)' % r, sep='\t')
        print
        sys.stdout.flush()
with open('remove_eol_crash_info.txt', 'r') as f:
    last = f.readline()
# start is the first OOPs ID to check, use the last one from the last run
for oops in oops_cf.get_range(start=last,
        columns=['DistroRelease','UserGroups'],
        buffer_size=2*1024):
    eol = False
    cleaned = False
    oops_id = oops[0]
    data = oops[1]
    release = data.get('DistroRelease', '')
    usergroups = data.get('UserGroups', '')
    if usergroups == '':
        cleaned = True
    print_totals()
    counts += 1
    # Stacktrace and ThreadStacktrace should not be in the OOPS table as
    # submit.py removes them, but try to remove it just in case.
    oops_cf.remove(oops_id, columns=never_needed_columns)
    # For EoL releases remove the columns that a developer would not want to see.
    if release in ('Ubuntu 12.10',
                   'Ubuntu 13.04', 'Ubuntu 13.10',
                   'Ubuntu 14.10'
                   'Ubuntu 15.04', 'Ubuntu 15.10',
                   'Ubuntu 16.10',
                   'Ubuntu 17.04', 'Ubuntu 17.10',
                   'Ubuntu 18.10',
                   'Ubuntu 19.04', 'Ubuntu 19.10'):
        eol = True
        if cleaned:
            continue
        print('Data removed for EoL release %s http://errors.ubuntu.com/oops/%s' %
              (release.strip('Ubuntu '), oops_id))
        oops_cf.remove(oops_id, columns=unneeded_columns)
    # For testing. ;-)
    #if counts >= 300000:
    # One hour
    if counts >= 19200:
        with open('remove_eol_crash_info.txt', 'w') as f:
            f.write(oops_id)
        break
print_totals(force=True)
print("Done!")
