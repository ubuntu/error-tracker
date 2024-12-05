#!/usr/bin/python
# -*- coding: utf-8 -*-
# 
# Copyright © 2011-2013 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation; version 3 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero Public License for more details.
# 
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import amqplib.client_0_8 as amqp
import logging
import os
import random
import shutil
import socket
import utils

from datetime import datetime

from daisy import config
from daisy.metrics import get_metrics

metrics = get_metrics('daisy.%s' % socket.gethostname())
logger = logging.getLogger('gunicorn.error')

oops_select = None
indexes_insert = None
_cached_swift = None
_cached_s3 = None

def write_policy_allow(oops_id, bytes_used, provider_data):
    if (provider_data.get('usage_max_mb')):
        usage_max = provider_data['usage_max_mb']*1024*1024
        # Random Early Drop policy: random drop with p-probality as:
        # 0 if <50%, then linearly (50%,100%) -> (0,1)
        if ((50+random.randint(0,49)) < (100*bytes_used/usage_max)):
            logger.info('Skipping oops_id={oops_id} save to type={st_type}, '
                'bytes_used={bytes_used}, usage_max={usage_max}'.format(
                  oops_id = oops_id,
                  st_type = provider_data['type'],
                  bytes_used = bytes_used,
                  usage_max = usage_max))
            metrics.meter('submit_core.random_early_drop')
            return False
    return True

def swift_delete_ignoring_error(swift_cmd, bucket, oops_id):
    from subprocess import check_call, CalledProcessError
    swift_delete_cmd = swift_cmd + ['delete', bucket, oops_id]
    try:
        check_call(swift_delete_cmd)
    except CalledProcessError:
        pass

def write_to_swift(environ, fileobj, oops_id, provider_data):
    '''Write the core file to OpenStack Swift.'''
    from subprocess import check_call, CalledProcessError

    swift_cmd = ['/usr/bin/swift',
                 '--os-auth-url', '%s' % provider_data['os_auth_url'],
                 '--os-username', '%s' % provider_data['os_username'],
                 '--os-password', '%s' % provider_data['os_password'],
                 '--os-tenant-name', '%s' % provider_data['os_tenant_name'],
                 '--os-region-name', '%s' % provider_data['os_region_name'],
                 '--os-project-name', '%s' % provider_data['os_tenant_name'],
                 '--auth-version', '3.0']
    bucket = provider_data['bucket']
    swift_post_cmd = swift_cmd + ['post', bucket]
    try:
        check_call(swift_post_cmd)
    except CalledProcessError:
        return False
    try:
        coredir = '/tmp/cores-%s' % os.getpid()
        if not os.path.exists(coredir):
            os.mkdir(coredir)
        import tempfile
        with tempfile.NamedTemporaryFile(dir=coredir) as t:
            while True:
                chunk = fileobj.read(1024*1024)
                if not chunk:
                    break
                t.write(chunk)
            t.flush()
            t.seek(0)
            t_size = os.path.getsize(t.name)
            msg = '%s has a %i byte core file' % (oops_id, t_size)
            logger.info(msg)
            swift_upload_cmd = swift_cmd + ['upload', '--object-name',
                                            oops_id, bucket,
                                            os.path.join(coredir, t.name)]
            check_call(swift_upload_cmd)
    except CalledProcessError as e:
        swift_delete_ignoring_error(swift_cmd, bucket, oops_id)
        msg = 'CalledProcessError when trying to add (%s) to bucket: %s' % \
               (oops_id, str(e.returncode))
        logger.info(msg)
        return False
    except IOError as e:
        swift_delete_ignoring_error(swift_cmd, bucket, oops_id)
        msg = 'IOError when trying to add (%s) to bucket: %s' % \
               (oops_id, str(e))
        logger.info(msg)
        return False
    msg = 'CORE for (%s) written to bucket' % (oops_id)
    logger.info(msg)
    return True

def s3_delete_ignoring_error(bucket, oops_id):
    from boto.exception import S3ResponseError
    try:
        bucket.delete_key(oops_id)
    except S3ResponseError:
        pass

def write_to_s3(fileobj, oops_id, provider_data):
    global _cached_s3
    '''Write the core file to Amazon S3.'''
    from boto.s3.connection import S3Connection
    from boto.exception import S3ResponseError

    if not _cached_s3:
        _cached_s3 = S3Connection(
                        aws_access_key_id=provider_data['aws_access_key'],
                        aws_secret_access_key=provider_data['aws_secret_key'],
                        host=provider_data['host'])
    try:
        bucket = _cached_s3.get_bucket(provider_data['bucket'])
    except S3ResponseError:
        bucket = _cached_s3.create_bucket(provider_data['bucket'])

    key = bucket.new_key(oops_id)
    try:
        key.set_contents_from_stream(fileobj)
    except IOError, e:
        s3_delete_ignoring_error(bucket, oops_id)
        if e.message == 'request data read error':
            return False
        else:
            raise
    except S3ResponseError:
        s3_delete_ignoring_error(bucket, oops_id)
        return False

    return True

def write_to_local(fileobj, oops_id, provider_data):
    '''Write the core file to local.'''

    path = os.path.join(provider_data['path'], oops_id)
    if (provider_data.get('usage_max_mb')):
        fs_stats = os.statvfs(provider_data['path'])
        bytes_used = (fs_stats.f_blocks-fs_stats.f_bavail)*fs_stats.f_bsize;
        if (not write_policy_allow(oops_id, bytes_used, provider_data)):
            return False
    copied = False
    with open(path, 'w') as fp:
        try:
            shutil.copyfileobj(fileobj, fp, 512)
            copied = True
        except IOError, e:
            if e.message != 'request data read error':
                raise

    if copied:
        os.chmod(path, 0o666)
        return True
    else:
        try:
            os.remove(path)
        except OSError:
            pass
        return False

def write_to_storage_provider(environ, fileobj, uuid):
    # We trade deteriminism for forgetfulness and make up for it by passing the
    # decision along with the UUID as part of the queue message.
    r = random.randint(1, 100)
    provider = None
    for key, ranges in config.write_weight_ranges.iteritems():
        if r >= (ranges[0]*100) and r <= (ranges[1]*100):
            provider = key
            provider_data = config.core_storage[key]
            break

    written = False
    message = uuid
    t = provider_data['type']
    if t == 'swift':
        written = write_to_swift(environ, fileobj, uuid, provider_data)
    elif t == 's3':
        written = write_to_s3(fileobj, uuid, provider_data)
    elif t == 'local':
        written = write_to_local(fileobj, uuid, provider_data)

    message = '%s:%s' % (message, provider)

    if written:
        return message
    else:
        metrics.meter('storage_write_error')
        return None

def write_to_amqp(message, arch):
    queue = 'retrace_%s' % arch
    try:
        if config.amqp_username and config.amqp_password:
            channel = amqp.Connection(host=config.amqp_host,
                                      userid=config.amqp_username,
                                      password=config.amqp_password).channel()
        else:
            channel = amqp.Connection(host=config.amqp_host).channel()
    except utils.amqplib_error_types as e:
        if utils.is_amqplib_connection_error(e):
            # Could not connect
            return False
        # Unknown error mode : don't hide it.
        raise
    if not channel:
        return False
    try:
        channel.queue_declare(queue=queue, durable=True, auto_delete=False)
        # We'll use this timestamp to measure how long it takes to process a
        # retrace, from receiving the core file to writing the data back to
        # Cassandra.
        body = amqp.Message(message, timestamp=datetime.utcnow())
        # Persistent
        body.properties['delivery_mode'] = 2
        channel.basic_publish(body, exchange='', routing_key=queue)
        msg = '%s added to %s queue' % (message.split(':')[0], queue)
        logger.info(msg)
        queued = True
    except utils.amqplib_error_types as e:
        if utils.is_amqplib_connection_error(e):
            # Could not connect / interrupted connection
            queued = False
        # Unknown error mode : don't hide it.
        raise
    finally:
        channel.close()
    return queued

def submit(_session, environ, fileobj, uuid, arch):
    global oops_select
    if not oops_select:
        oops_select = _session.prepare('SELECT value FROM "OOPS" WHERE key = ? AND column1 = ? LIMIT 1')
    try:
        # every OOPS will have a SystemIdentifier
        sys_id_results = _session.execute(oops_select,
                                          [uuid, 'SystemIdentifier'])
        sys_id = [row[0] for row in sys_id_results][0]
    except IndexError:
        # Due to Cassandra's eventual consistency model, we may receive
        # the core dump before the OOPS has been written to all the
        # nodes. This is acceptable, as we'll just ask the next user
        # for a core dump.
        msg = 'No OOPS found for this core dump.'
        logger.info(msg)
        metrics.meter('submit_core.no_matching_oops')
        return (False, msg)

    # Only accept core files for architectures for which we have retracers,
    # this also won't write weird things like, (md64 or md64, which happened
    # in 2021.
    if arch not in ('amd64', 'arm64', 'armhf', 'i386'):
        return (False, '')

    message = write_to_storage_provider(environ, fileobj, uuid)
    if not message:
        # If not written to storage then write to log file
        msg = 'Failure to write OOPS %s to storage provider' % \
            (uuid)
        logger.info(msg)
        # Return False and whoopsie will not try and upload it again.
        # However, we'll ask for a core file for a different crash with the
        # same SAS.
        return (False, '')
    queued = write_to_amqp(message, arch)
    if not queued:
        # If not written to amqp then write to log file
        msg = 'Failure to write to amqp retrace queue %s %s' % \
            (arch, message)
        logger.info(msg)

    try:
        addr_sig_results = _session.execute(oops_select,
                                            [uuid, 'StacktraceAddressSignature'])
        addr_sig = [row[0] for row in addr_sig_results][0]
    except IndexError:
        addr_sig = ''
        pass
    # N.B. a report without an initial StacktraceAddressSignature won't be
    # written to the retracing index which is correct because there isn't a
    # way to identify similar ones without a SAS.
    if addr_sig and queued:
        global indexes_insert
        if not indexes_insert:
            indexes_insert = _session.prepare('INSERT INTO "Indexes" \
                (key, column1, value) VALUES (?, ?, ?)')
        _session.execute(indexes_insert,
                         ['retracing', addr_sig, '0x'])

    return (True, uuid)
