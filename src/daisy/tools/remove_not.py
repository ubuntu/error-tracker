#!/usr/bin/python
import pycassa
from daisy import config

creds = {'username': config.cassandra_username,
         'password': config.cassandra_password}
pool = pycassa.ConnectionPool(config.cassandra_keyspace,
                              config.cassandra_hosts, timeout=15,
                              credentials=creds)
bucketmetadata_cf = pycassa.ColumnFamily(pool, 'BucketMetadata')

def main():
    for key, column_data in bucketmetadata_cf.get_range(columns=['LastSeen', 'FirstSeen']):
        if column_data['LastSeen'] == '(not' and key:
            print 'fixing', key
            bucketmetadata_cf.insert(key, {'LastSeen':''})
        if column_data['FirstSeen'] == '(not' and key:
            print 'fixing', key
            bucketmetadata_cf.insert(key, {'FirstSeen':''})

if __name__ == '__main__':
    main()
