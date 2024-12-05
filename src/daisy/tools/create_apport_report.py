#!/usr/bin/python

import os
import pycassa
import sys

from apport import report
from daisy import config
from subprocess import Popen, PIPE, check_output, CalledProcessError

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              credentials=creds)

oops_cf = pycassa.ColumnFamily(pool, 'OOPS')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('usage: oops file-path [core]')
        sys.exit(1)

    core = None
    core_file = None
    if len(sys.argv) == 4:
        core_file = sys.argv[3]
    oops = oops_cf.get(sys.argv[1])
    report = report.Report()
    for k in oops:
        report[k] = oops[k]
    if core_file:
        with open('%s.coredump' % core_file, 'wb') as fp:
            # test to see if the core_file can be base64 decoded
            try:
                output = check_output(['base64', '-d', core_file])
                p1 = Popen(['base64', '-d', core_file], stdout=PIPE)
            except CalledProcessError:
                # if base64 decoding doesn't work maybe it was decoded for us
                p1 = Popen(['cat', core_file], stdout=PIPE)
            # Set stderr to PIPE so we get output in the result tuple.
            p2 = Popen(['zcat'], stdin=p1.stdout, stdout=fp, stderr=PIPE)
            ret2 = p2.communicate()
        report['CoreDump'] = ('%s.coredump' % core_file,)
    fp = open(sys.argv[2], 'wb')
    report.write(fp)
    if core_file:
        os.remove('%s.coredump' % core_file)
