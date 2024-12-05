#!/usr/bin/python
import pycassa
import sys
from datetime import datetime, timedelta

from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=10,
                              credentials=creds)
oops_cf = pycassa.ColumnFamily(pool, 'OOPS')

old_date = datetime.today() - timedelta(days=7)
count = 0

for oops, oops_data in oops_cf.get_range(columns=['Date','Package'],
        row_count=5000):
    if count >= 10:
        sys.exit(0)
    date_str = oops_data.get('Date', '')
    try:
        date = datetime.strptime(date_str, '%a %b %d %H:%M:%S %Y')
    except ValueError:
        continue
    if date.date() <= old_date.date():
        continue
    pkg = oops_data.get('Package', '')
    try:
        package = pkg.split()[0]
    except IndexError:
        package = ''
    if package.startswith('linux-image-'):
        continue
    try:
        version = pkg.split()[1:]
    except IndexError:
        version = ''
    if package and version:
        continue
    if not package:
        print("missing package:")
    elif package and not version:
        print("missing version:")
    print("  https://errors.ubuntu.com/oops/%s" % oops)
    count += 1
