#!/usr/bin/python

import unittest
import mock
import bson
import apport
from cStringIO import StringIO
from testtools import TestCase
from oopsrepository.testing.cassandra import TemporaryOOPSDB
import pycassa
import tempfile
import shutil
import os
import time

from oopsrepository import oopses
from oopsrepository import schema as oopsschema
from oopsrepository import config as oopsconfig
from daisy import config
from daisy import submit
from daisy import schema
from daisy import wsgi

# SHA-512 of the system-uuid
sha512_system_uuid = ('/d78abb0542736865f94704521609c230dac03a2f369d043ac212d6'
                      '933b91410e06399e37f9c5cc88436a31737330c1c8eccb2c2f9f374'
                      'd62f716432a32d50fac')

class TestSubmission(TestCase):
    def setUp(self):
        super(TestSubmission, self).setUp()
        self.start_response = mock.Mock()

        # Set up daisy schema.
        os.environ['OOPS_HOST'] = config.cassandra_hosts[0]
        self.keyspace = self.useFixture(TemporaryOOPSDB()).keyspace
        os.environ['OOPS_KEYSPACE'] = self.keyspace
        config.cassandra_keyspace = self.keyspace
        self.creds = {'username': config.cassandra_username,
                      'password': config.cassandra_password}
        schema.create()

        # Set up oopsrepository schema.
        oops_config = oopsconfig.get_config()
        oops_config['username'] = config.cassandra_username
        oops_config['password'] = config.cassandra_password
        oopsschema.create(oops_config)

        # Clear singletons.
        wsgi._pool = None
        oopses._connection_pool = None
        submit.oops_config = oops_config

class TestCrashSubmission(TestSubmission):

    def test_bogus_submission(self):
        environ = {'PATH_INFO': '/', 'wsgi.input': StringIO('')}
        wsgi.app(environ, self.start_response)
        self.assertEqual(self.start_response.call_args[0][0], '400 Bad Request')

    def test_python_submission(self):
        '''Ensure that a Python crash is accepted, bucketed, and that the
        retracing ColumnFamilies remain untouched.'''

        report = apport.Report()
        report['ProblemType'] = 'Crash'
        report['InterpreterPath'] = '/usr/bin/python'
        report['ExecutablePath'] = '/usr/bin/foo'
        report['DistroRelease'] = 'Ubuntu 12.04'
        report['Package'] = 'ubiquity 2.34'
        report['Traceback'] = ('Traceback (most recent call last):\n'
                               '  File "/usr/bin/foo", line 1, in <module>\n'
                               '    sys.exit(1)')
        report_bson = bson.BSON.encode(report.data)
        report_io = StringIO(report_bson)
        environ = { 'CONTENT_TYPE' : 'application/octet-stream',
                    'PATH_INFO' : sha512_system_uuid,
                    'wsgi.input' : report_io }

        wsgi.app(environ, self.start_response)
        self.assertEqual(self.start_response.call_args[0][0], '200 OK')

        pool = pycassa.ConnectionPool(self.keyspace, config.cassandra_hosts,
                                      credentials=self.creds)
        oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
        bucket_cf = pycassa.ColumnFamily(pool, 'Bucket')
        # Ensure the crash was bucketed:
        oops_id = oops_cf.get_range().next()[0]
        crash_signature = '/usr/bin/foo:    sys.exit(1):/usr/bin/foo@1'
        self.assertEqual(pycassa.util.uuid.UUID(oops_id), bucket_cf.get(crash_signature).keys()[0])

        # A Python crash shouldn't touch the retracing CFs:
        for fam in ('AwaitingRetrace', 'Stacktrace', 'Indexes'):
            cf = pycassa.ColumnFamily(pool, fam)
            self.assertEqual([x for x in cf.get_range()], [])
        cf = pycassa.ColumnFamily(pool, 'DayBucketsCount')
        counts = [x for x in cf.get_range()]
        day_key = time.strftime('%Y%m%d', time.gmtime())
        resolutions = (day_key, day_key[:4], day_key[:6])
        release = report['DistroRelease']
        keys = []
        for resolution in resolutions:
            keys.append('%s:%s' % (release, resolution))
        for resolution in resolutions:
            keys.append('%s:ubiquity:%s' % (release, resolution))
        for resolution in resolutions:
            keys.append('%s:ubiquity:2.34:%s' % (release, resolution))
        for resolution in resolutions:
            keys.append('ubiquity:2.34:%s' % resolution)
        'ubiquity:2.34'

        for key in keys:
            found = False
            for count in counts:
                if count[0] == key:
                    found = True
            self.assertTrue(found, 'Could not find %s' % key)
            for count in counts:
                self.assertEqual(count[1].values(), [1])

    def test_kerneloops_submission(self):
        oops_text = '''BUG: unable to handle kernel paging request at ffffb4ff
IP: [<c11e4690>] ext4_get_acl+0x80/0x210
*pde = 01874067 *pte = 00000000 
Oops: 0000 [#1] SMP 
Modules linked in: bnep rfcomm bluetooth dm_crypt olpc_xo1 scx200_acb snd_cs5535audio snd_ac97_codec ac97_bus snd_pcm snd_seq_midi snd_rawmidi snd_seq_midi_event snd_seq snd_timer snd_seq_device snd cs5535_gpio soundcore snd_page_alloc binfmt_misc geode_aes cs5535_mfd geode_rng msr vesafb usbhid hid 8139too pata_cs5536 8139cp

Pid: 1798, comm: gnome-session-c Not tainted 3.0.0-11-generic #17-Ubuntu First International Computer, Inc.  ION603/ION603
EIP: 0060:[<c11e4690>] EFLAGS: 00010286 CPU: 0
EIP is at ext4_get_acl+0x80/0x210
EAX: f5d3009c EBX: f5d30088 ECX: 00000000 EDX: f5d301d8
ESI: ffffb4ff EDI: 00008000 EBP: f29b3dc8 ESP: f29b3da4
 DS: 007b ES: 007b FS: 00d8 GS: 00e0 SS: 0068
Process gnome-session-c (pid: 1798, ti=f29b2000 task=f2bd72c0 task.ti=f29b2000)
Stack:
 f29b3db0 c113bb90 f5d301d8 f29b3de4 c11b9016 f5d3009c f5d30088 f5d30088
 00000001 f29b3ddc c11e4cca 00000001 f5d30088 000081ed f29b3df0 c11313b7
 00000021 00000021 f5d30088 f29b3e08 c1131b45 c11e4c80 f5d30088 00000021
Call Trace:
 [<c113bb90>] ? d_splice_alias+0x40/0x50
 [<c11b9016>] ? ext4_lookup.part.30+0x56/0x120
 [<c11e4cca>] ext4_check_acl+0x4a/0x90
 [<c11313b7>] acl_permission_check+0x97/0xa0
 [<c1131b45>] generic_permission+0x25/0xc0
 [<c11e4c80>] ? ext4_xattr_set_acl+0x160/0x160
 [<c1131c79>] inode_permission+0x99/0xd0
 [<c11e4c80>] ? ext4_xattr_set_acl+0x160/0x160
 [<c1131d1b>] may_open+0x6b/0x110
 [<c1134566>] do_last+0x1a6/0x640
 [<c113595d>] path_openat+0x9d/0x350
 [<c10de692>] ? unlock_page+0x42/0x50
 [<c10fb960>] ? __do_fault+0x3b0/0x4b0
 [<c1135c41>] do_filp_open+0x31/0x80
 [<c124c743>] ? aa_dup_task_context+0x33/0x60
 [<c1250eed>] ? apparmor_cred_prepare+0x2d/0x50
 [<c112e9ef>] open_exec+0x2f/0x110
 [<c112eef7>] ? check_unsafe_exec+0xb7/0xf0
 [<c112efba>] do_execve_common+0x8a/0x270
 [<c112f1b7>] do_execve+0x17/0x20
 [<c100a0a7>] sys_execve+0x37/0x70
 [<c15336ae>] ptregs_execve+0x12/0x18
 [<c152c8d4>] ? syscall_call+0x7/0xb
Code: 8d 76 00 8d 93 54 01 00 00 8b 32 85 f6 74 e2 8d 43 14 89 55 e4 89 45 f0 e8 2e 7e 34 00 8b 55 e4 8b 32 83 fe ff 74 07 85 f6 74 03 <3e> ff 06 8b 45 f0 e8 25 19 e4 ff 90 83 fe ff 75 b5 81 ff 00 40 
EIP: [<c11e4690>] ext4_get_acl+0x80/0x210 SS:ESP 0068:f29b3da4
CR2: 00000000ffffb4ff
---[ end trace b567e6a3070ffb42 ]---'''
        bucket = 'kernel paging request:ext4_get_acl+0x80/0x210:ext4_check_acl+0x4a/0x90:acl_permission_check+0x97/0xa0:generic_permission+0x25/0xc0:inode_permission+0x99/0xd0:may_open+0x6b/0x110:do_last+0x1a6/0x640:path_openat+0x9d/0x350:do_filp_open+0x31/0x80:open_exec+0x2f/0x110:do_execve_common+0x8a/0x270:do_execve+0x17/0x20:sys_execve+0x37/0x70:ptregs_execve+0x12/0x18'
        report = apport.Report()
        report['ProblemType'] = 'KernelOops'
        report['OopsText'] = oops_text
        report_bson = bson.BSON.encode(report.data)
        report_io = StringIO(report_bson)
        environ = { 'CONTENT_TYPE' : 'application/octet-stream',
                    'PATH_INFO' : sha512_system_uuid,
                    'wsgi.input' : report_io }

        wsgi.app(environ, self.start_response)
        pool = pycassa.ConnectionPool(self.keyspace, config.cassandra_hosts,
                                      credentials=self.creds)
        oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
        bucket_cf = pycassa.ColumnFamily(pool, 'Bucket')
        oops_id = oops_cf.get_range().next()[0]
        bucket_id, unused_oops_id = bucket_cf.get_range().next()
        self.assertEqual(bucket_id, bucket)

class TestBinarySubmission(TestCrashSubmission):
    def setUp(self):
        super(TestBinarySubmission, self).setUp()
        self.stack_addr_sig = (
            '/usr/bin/foo:11:x86_64/lib/x86_64-linux-gnu/libc-2.15.so+e4d93:'
            '/usr/bin/foo+1e071')
        report = apport.Report()
        report['ProblemType'] = 'Crash'
        report['StacktraceAddressSignature'] = self.stack_addr_sig
        report['ExecutablePath'] = '/usr/bin/foo'
        report['Package'] = 'whoopsie 1.2.3'
        report['DistroRelease'] = 'Ubuntu 12.04'
        report['StacktraceTop'] = 'raise () from /lib/i386-linux-gnu/libc.so.6'
        report['Signal'] = '11'
        report_bson = bson.BSON.encode(report.data)
        report_io = StringIO(report_bson)
        self.environ = { 'CONTENT_TYPE' : 'application/octet-stream',
                         'PATH_INFO' : sha512_system_uuid,
                         'wsgi.input' : report_io }

    def test_binary_submission_not_retraced(self):
        '''If a binary crash has been submitted that we do not have a core file
        for, either already retraced or awaiting to be retraced.'''

        resp = wsgi.app(self.environ, self.start_response)[0]
        self.assertEqual(self.start_response.call_args[0][0], '200 OK')
        # We should get back a request for the core file:
        self.assertTrue(resp.endswith(' CORE'))

        # It should end up in the AwaitingRetrace CF queue.
        pool = pycassa.ConnectionPool(self.keyspace, config.cassandra_hosts,
                                      credentials=self.creds)
        awaiting_retrace_cf = pycassa.ColumnFamily(pool, 'AwaitingRetrace')
        oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
        oops_id = oops_cf.get_range().next()[0]
        self.assertEqual(
            awaiting_retrace_cf.get(self.stack_addr_sig).keys()[0], oops_id)

    def test_binary_submission_retrace_queued(self):
        '''If a binary crash has been submitted that we do have a core file
        for, but it has not been retraced yet.'''
        # Lets pretend we've seen the stacktrace address signature before, and
        # have received a core file for it, but have not finished retracing it:
        pool = pycassa.ConnectionPool(self.keyspace, config.cassandra_hosts,
                                      credentials=self.creds)
        awaiting_retrace_cf = pycassa.ColumnFamily(pool, 'AwaitingRetrace')
        oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
        indexes_cf = pycassa.ColumnFamily(pool, 'Indexes')
        indexes_cf.insert('retracing', {self.stack_addr_sig : ''})

        resp = wsgi.app(self.environ, self.start_response)[0]
        self.assertEqual(self.start_response.call_args[0][0], '200 OK')
        # We should not get back a request for the core file:
        self.assertEqual(resp, '')
        # Ensure the crash was bucketed and added to the AwaitingRetrace CF
        # queue:
        oops_id = oops_cf.get_range().next()[0]
        self.assertEqual(
            awaiting_retrace_cf.get(self.stack_addr_sig).keys()[0], oops_id)

    def test_binary_submission_already_retraced(self):
        '''If a binary crash has been submitted that we have a fully-retraced
        core file for.'''
        pool = pycassa.ConnectionPool(self.keyspace, config.cassandra_hosts,
                                      credentials=self.creds)
        indexes_cf = pycassa.ColumnFamily(pool, 'Indexes')
        bucket_cf = pycassa.ColumnFamily(pool, 'Bucket')
        oops_cf = pycassa.ColumnFamily(pool, 'OOPS')

        indexes_cf.insert('crash_signature_for_stacktrace_address_signature',
                          {self.stack_addr_sig : 'fake-crash-signature'})

        resp = wsgi.app(self.environ, self.start_response)[0]
        self.assertEqual(self.start_response.call_args[0][0], '200 OK')
        # We should not get back a request for the core file:
        self.assertEqual(resp, '')
        
        # Make sure 'foo' ends up in the bucket.
        oops_id = oops_cf.get_range().next()[0]
        bucket_contents = bucket_cf.get('fake-crash-signature').keys()
        self.assertEqual(bucket_contents, [pycassa.util.uuid.UUID(oops_id)])

class TestCoreSubmission(TestSubmission):
    def setUp(self):
        super(TestCoreSubmission, self).setUp()
        self.conn_mock = mock.MagicMock()
        # TODO in the future, we may want to just set up a local Rabbit MQ,
        # like we do with Cassandra.
        amqp_connection = mock.patch('amqplib.client_0_8.Connection', self.conn_mock)
        amqp_connection.start()
        self.msg_mock = mock.MagicMock()
        amqp_msg = mock.patch('amqplib.client_0_8.Message', self.msg_mock)
        amqp_msg.start()
        self.addCleanup(amqp_msg.stop)
        self.addCleanup(amqp_connection.stop)

    def test_core_submission(self):
        data = 'I am an ELF binary. No, really.'
        core_io = StringIO(data)
        uuid = '12345678-1234-5678-1234-567812345678'
        environ = {'QUERY_STRING' : 'uuid=%s&arch=amd64' % uuid,
                   'CONTENT_TYPE' : 'application/octet-stream',
                   'wsgi.input' : core_io,
                   'PATH_INFO': '/%s/submit-core/amd64' % uuid}
        stack_addr_sig = (
            '/usr/bin/foo:11:x86_64/lib/x86_64-linux-gnu/libc-2.15.so+e4d93:'
            '/usr/bin/foo+1e071')
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path)
        pool = pycassa.ConnectionPool(self.keyspace, config.cassandra_hosts,
                                      credentials=self.creds)
        oops_cf = pycassa.ColumnFamily(pool, 'OOPS')
        oops_cf.insert(uuid, {'StacktraceAddressSignature' : stack_addr_sig})

        with mock.patch('daisy.submit_core.config', autospec=True) as cfg:
            cfg.core_storage = {'local': {'type':'local', 'path':path}}
            cfg.storage_write_weights = {'local': 1.0}
            cfg.write_weight_ranges = {'local': (0.0, 1.0)}
            wsgi.app(environ, self.start_response)
        self.assertEqual(self.start_response.call_args[0][0], '200 OK')

        # Did we actually write the core file to disk?
        with open(os.path.join(path, uuid)) as fp:
            contents = fp.read()
        self.assertEqual(contents, data)

        # Did we put the crash on the retracing queue?
        channel = self.conn_mock.return_value.channel
        basic_publish_call = channel.return_value.basic_publish.call_args
        kwargs = basic_publish_call[1]
        self.assertEqual(kwargs['routing_key'], 'retrace_amd64')
        self.assertEqual(kwargs['exchange'], '')
        msg = '%s:local' % uuid
        self.assertEqual(self.msg_mock.call_args[0][0], msg)
        self.assertTrue(os.path.exists(os.path.join(path, uuid)))

        # did we mark this as retracing in Cassandra?
        indexes_cf = pycassa.ColumnFamily(pool, 'Indexes')
        indexes_cf.get('retracing', [stack_addr_sig])
    def test_core_submission_s3(self):
        from daisy import submit_core
        provider_data = {
            'aws_access_key': 'access',
            'aws_secret_key': 'secret',
            'host': 'does-not-exist.ubuntu.com',
            'bucket': 'core_files',
        }
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            fp.write('Core file contents.')
            fp.flush()
            with open(fp.name, 'r') as f:
                with mock.patch('boto.s3.connection.S3Connection') as s3con:
                    get_bucket = s3con.return_value.get_bucket
                    create_bucket = s3con.return_value.create_bucket
                    submit_core.write_to_s3(f, 'oops-id', provider_data)
                    # Did we grab from the correct bucket?
                    get_bucket.assert_called_with('core_files')
                    new_key = get_bucket.return_value.new_key
                    # Did we create a new key in the bucket for the OOPS ID?
                    new_key.assert_called_with('oops-id')

                    # Bucket does not exist.
                    from boto.exception import S3ResponseError
                    get_bucket.side_effect = S3ResponseError('400', 'No reason')
                    submit_core.write_to_s3(f, 'oops-id', provider_data)
                    get_bucket.assert_called_with('core_files')
                    # Did we create the non-existent bucket?
                    create_bucket.assert_called_with('core_files')

if __name__ == '__main__':
    unittest.main()
