#!/usr/bin/python

import shutil
import tempfile
import time
import uuid
from pathlib import Path

import apport
import bson
import pytest

from daisy.app import app as daisy_flask_app
from errortracker import amqp_utils, cassandra_schema, swift_utils

# SHA-512 of the system-uuid
sha512_system_uuid = (
    "d78abb0542736865f94704521609c230dac03a2f369d043ac212d6"
    "933b91410e06399e37f9c5cc88436a31737330c1c8eccb2c2f9f374"
    "d62f716432a32d50fac"
)


@pytest.fixture()
def app():
    daisy_flask_app.config.update(
        {
            "TESTING": True,
        }
    )
    yield daisy_flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def path():
    p = tempfile.mkdtemp()
    yield Path(p)
    shutil.rmtree(p)


class TestCrashSubmission:
    def test_index_not_found(self, client):
        response = client.post("/")
        assert response.status_code == 404

    def test_bogus_submission(self, client, temporary_db):
        response = client.post("/my_super_awesome_system_id", data=b"")
        assert response.status_code == 400
        assert b"Invalid BSON" in response.data

    def test_submission_eol_release(self, client, temporary_db):
        """Ensure that a Python crash is accepted, bucketed, and that the
        retracing ColumnFamilies remain untouched."""

        report = apport.Report()
        report["ProblemType"] = "Crash"
        report["InterpreterPath"] = "/usr/bin/python"
        report["ExecutablePath"] = "/usr/bin/foo"
        report["DistroRelease"] = "Ubuntu 12.04"
        report["Package"] = "ubiquity 2.34"
        report["Traceback"] = (
            "Traceback (most recent call last):\n"
            '  File "/usr/bin/foo", line 1, in <module>\n'
            "    sys.exit(1)"
        )
        report_bson = bson.BSON.encode(report.data)
        response = client.post(f"/{sha512_system_uuid}", data=report_bson)
        assert b"Ubuntu 12.04 is End of Life" in response.data
        assert response.status_code == 400

    def test_python_submission(self, client, temporary_db):
        """Ensure that a Python crash is accepted, bucketed, and that the
        retracing ColumnFamilies remain untouched."""
        report = apport.Report()
        report["ProblemType"] = "Crash"
        report["InterpreterPath"] = "/usr/bin/python"
        report["ExecutablePath"] = "/usr/bin/foo"
        report["DistroRelease"] = "Ubuntu 24.04"
        report["Package"] = "ubiquity 2.34"
        report["Traceback"] = (
            "Traceback (most recent call last):\n"
            '  File "/usr/bin/foo", line 1, in <module>\n'
            "    sys.exit(1)"
        )
        report_bson = bson.BSON.encode(report.data)
        response = client.post(f"/{sha512_system_uuid}", data=report_bson)
        assert b" OOPSID" in response.data
        assert response.status_code == 200

        oops_id = response.data.decode().split(" ")[0]
        crash_signature = "/usr/bin/foo:    sys.exit(1):/usr/bin/foo@1"

        # Ensure the crash was bucketed:
        bucket = cassandra_schema.Bucket.all()[0]
        assert bucket.key == crash_signature
        assert str(bucket.column1) == oops_id

        # A Python crash shouldn't touch the retracing CFs:
        assert [] == list(cassandra_schema.AwaitingRetrace.all())
        assert [] == list(cassandra_schema.Stacktrace.all())
        assert [] == list(cassandra_schema.Indexes.all())

        now = time.gmtime()
        day_key = time.strftime("%Y%m%d", now)
        month_key = time.strftime("%Y%m", now)
        year_key = time.strftime("%Y", now)
        release = report["DistroRelease"]
        time_keys = (day_key, month_key, year_key)
        keys = []
        for time_key in time_keys:
            keys.append(f"{release}:{time_key}")
            keys.append(f"{release}:ubiquity:{time_key}")
            keys.append(f"{release}:ubiquity:2.34:{time_key}")
            keys.append(f"ubiquity:2.34:{time_key}")

        for key in keys:
            assert cassandra_schema.DayBucketsCount.get(key=key.encode()).value == 1

    def test_kerneloops_submission(self, client, temporary_db):
        oops_text = """BUG: unable to handle kernel paging request at ffffb4ff
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
---[ end trace b567e6a3070ffb42 ]---"""
        report = apport.Report()
        report["ProblemType"] = "KernelOops"
        report["Package"] = "linux"
        report["OopsText"] = oops_text
        report_bson = bson.BSON.encode(report.data)
        response = client.post(f"/{sha512_system_uuid}", data=report_bson)
        assert b" OOPSID" in response.data
        assert response.status_code == 200

        # XXX kernel crash bucketing not working yet
        # oops_id = response.data.decode().split(" ")[0]
        # crash_signature = "kernel paging request:ext4_get_acl+0x80/0x210:ext4_check_acl+0x4a/0x90:acl_permission_check+0x97/0xa0:generic_permission+0x25/0xc0:inode_permission+0x99/0xd0:may_open+0x6b/0x110:do_last+0x1a6/0x640:path_openat+0x9d/0x350:do_filp_open+0x31/0x80:open_exec+0x2f/0x110:do_execve_common+0x8a/0x270:do_execve+0x17/0x20:sys_execve+0x37/0x70:ptregs_execve+0x12/0x18"

        # Ensure the crash was bucketed:
        # bucket = cassandra_schema.Bucket.all()[0]
        # assert bucket.key == crash_signature
        # assert str(bucket.column1) == oops_id


class TestBinarySubmission:
    def setup_method(self):
        self.stack_addr_sig = (
            "/usr/bin/foo:11:x86_64/lib/x86_64-linux-gnu/libc-2.15.so+e4d93:/usr/bin/foo+1e071"
        )
        self.report = apport.Report()
        self.report["ProblemType"] = "Crash"
        self.report["StacktraceAddressSignature"] = self.stack_addr_sig
        self.report["ExecutablePath"] = "/usr/bin/foo"
        self.report["Package"] = "whoopsie 1.2.3"
        self.report["DistroRelease"] = "Ubuntu 24.04"
        self.report["StacktraceTop"] = "raise () from /lib/i386-linux-gnu/libc.so.6"
        self.report["Signal"] = "11"
        self.report_bson = bson.BSON.encode(self.report.data)

    def test_binary_submission_not_retraced(self, client, temporary_db):
        """If a binary crash has been submitted that we do not have a core file
        for, either already retraced or awaiting to be retraced."""
        self.setup_method()

        response = client.post(f"/{sha512_system_uuid}", data=self.report_bson)
        # We should get back a request for the core file:
        assert response.data.decode().endswith(" CORE")
        assert response.status_code == 200

        oops_id = response.data.decode().split(" ")[0]

        # It should end up in the AwaitingRetrace queue.
        retrace_queue = cassandra_schema.AwaitingRetrace.all()[0]
        assert retrace_queue.key == self.stack_addr_sig
        assert retrace_queue.column1 == oops_id

    def test_binary_submission_retrace_queued(self, client, temporary_db):
        """If a binary crash has been submitted that we do have a core file
        for, but it has not been retraced yet."""
        self.setup_method()

        # Lets pretend we've seen the stacktrace address signature before, and
        # have received a core file for it, but have not finished retracing it:
        cassandra_schema.AwaitingRetrace.create(key=self.stack_addr_sig, column1=str(uuid.uuid1()))
        cassandra_schema.Indexes.create(key=b"retracing", column1=self.stack_addr_sig, value=b"")

        response = client.post(f"/{sha512_system_uuid}", data=self.report_bson)
        # We should not get back a request for the core file:
        assert b" OOPSID" in response.data
        assert not response.data.decode().endswith(" CORE")
        assert response.status_code == 200

        oops_id = response.data.decode().split(" ")[0]

        # It should end up in the AwaitingRetrace queue.
        retrace_queue = cassandra_schema.AwaitingRetrace.all()
        found = False
        for r in retrace_queue:
            assert r.key == self.stack_addr_sig
            if r.column1 == oops_id:
                found = True
        assert found, f"{oops_id} not found in AwaitingRetrace"

    def test_binary_submission_already_retraced(self, client, temporary_db):
        """If a binary crash has been submitted that we have a fully-retraced
        core file for."""
        self.setup_method()

        cassandra_schema.Indexes.create(
            key=b"crash_signature_for_stacktrace_address_signature",
            column1=self.stack_addr_sig,
            value=b"fake-crash-signature",
        )
        cassandra_schema.Stacktrace.create(
            key=self.stack_addr_sig.encode(), column1="Stacktrace", value="fake full stacktrace"
        )
        cassandra_schema.Stacktrace.create(
            key=self.stack_addr_sig.encode(),
            column1="ThreadStacktrace",
            value="fake thread stacktrace",
        )

        response = client.post(f"/{sha512_system_uuid}", data=self.report_bson)
        # We should not get back a request for the core file:
        assert b" OOPSID" in response.data
        assert not response.data.decode().endswith(" CORE")
        assert response.status_code == 200

        oops_id = response.data.decode().split(" ")[0]

        # Make sure 'foo' ends up in the bucket.
        buckets = list(cassandra_schema.Bucket.filter(key="fake-crash-signature"))

        assert len(buckets) == 1
        assert oops_id == str(buckets[0].column1)


class TestCoreSubmission:
    def test_core_submission(self, client, temporary_db, path):
        data = "I am an ELF binary. No, really."
        uuid = "12345678-1234-5678-1234-567812345678"
        stack_addr_sig = (
            "/usr/bin/foo:11:x86_64/lib/x86_64-linux-gnu/libc-2.15.so+e4d93:/usr/bin/foo+1e071"
        )
        cassandra_schema.OOPS.create(
            key=uuid.encode(), column1="StacktraceAddressSignature", value=stack_addr_sig
        )
        cassandra_schema.OOPS.create(
            key=uuid.encode(), column1="SystemIdentifier", value=stack_addr_sig
        )

        response = client.post(f"/{uuid}/submit-core/amd64/{sha512_system_uuid}", data=data)

        # We should not get back a request for the core file:
        assert uuid.encode() == response.data
        assert response.status_code == 200

        # Did we actually write the core file to swift?
        _, contents = swift_utils.get_swift_client().get_object("cores", uuid)
        assert contents.decode() == data

        with amqp_utils.get_connection() as c:
            assert c is not None, "Could not connect to RabbitMQ"

            ch = c.channel()

            def on_message(message):
                assert message.body == f"{uuid}:swift"
                ch.basic_ack(message.delivery_tag)

            ch.basic_consume(queue="retrace_amd64", callback=on_message)
            c.drain_events()  # only one event, and in the tests, no need for the usual infinite loop
            ch.close()

        # did we mark this as retracing in Cassandra?
        assert cassandra_schema.Indexes.get(key=b"retracing").column1 == stack_addr_sig
