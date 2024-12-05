import pycassa
from daisy import config
from daisy.constants import RAMP_UP
import datetime
import time
import sys

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=600,
                              max_retries=100, credentials=creds)

errorsbyrelease = pycassa.ColumnFamily(pool, 'ErrorsByRelease')
uniquesys = pycassa.ColumnFamily(pool, 'UniqueSystemsForErrorsByRelease')

def weight(release='Ubuntu 12.04'):
    results = {}
    one_day = datetime.timedelta(days=1)
    today = datetime.datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - one_day
    working_date = yesterday - datetime.timedelta(days=180)

    while working_date <= yesterday:
        total = 0
        gen = errorsbyrelease.xget((release, working_date))
        found = False
        for oopsid, first_error_date in gen:
            day_difference = (working_date - first_error_date).days
            adj = min(day_difference, RAMP_UP) / float(RAMP_UP)
            total += adj
            found = True

        if found:
            s = uniquesys.get(release, columns=[working_date])[working_date]
            ts = time.mktime(working_date.timetuple())
            results[ts] = total / s

        working_date += one_day
    return results

if __name__ == '__main__':
    for ts, weighting in weight().iteritems():
        print '{x: %d, y: %d}' % (ts * 1000, weighting)
