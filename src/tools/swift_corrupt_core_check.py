#!/usr/bin/python3

# iterate over the core files in swift and check to see if they are corrupt
# if they are we won't be able to retrace them so remove them from swift

import os
import sys
import tempfile
from subprocess import PIPE, Popen

import swiftclient

from errortracker import config, swift_utils

# get container returns a max of 10000 listings, if an integer is not given
# lets get everything not 10k.
limit = None
unlimited = False
if len(sys.argv) == 2:
    limit = int(sys.argv[1])
else:
    unlimited = True

swift_client = swift_utils.get_swift_client()
bucket = config.swift_bucket

gdb_which = Popen(["which", "gdb"], stdout=PIPE, universal_newlines=True)
gdb_path = gdb_which.communicate()[0].strip()

count = 0
unqueued_count = 0


def rm_eff(path):
    """Remove ignoring -ENOENT."""
    try:
        os.remove(path)
    except OSError as e:
        if e.errno != 2:
            raise


for container in swift_client.get_container(container=bucket, limit=limit, full_listing=unlimited):
    # the dict is the metadata for the container
    if isinstance(container, dict):
        continue
    if limit:
        toreview = container[:limit]
    else:
        toreview = container
    for core in toreview:
        uuid = core["name"]
        count += 1
        fmt = "-{}.{}.oopsid".format("swift", uuid)
        fd, path = tempfile.mkstemp(fmt)
        os.close(fd)
        try:
            headers, body = swift_client.get_object(bucket, uuid, resp_chunk_size=65536)
            with open(path, "wb") as fp:
                for chunk in body:
                    fp.write(chunk)
        except swiftclient.client.ClientException as e:
            if "404 Not Found" in str(e):
                print("Couldn't get the core file!")
                continue
        core_file = "%s.core" % path
        with open(core_file, "wb") as fp:
            # print('Decompressing to %s' % core_file)
            p1 = Popen(["base64", "-d", path], stdout=PIPE)
            # Set stderr to PIPE so we get output in the result tuple.
            p2 = Popen(["zcat"], stdin=p1.stdout, stdout=fp, stderr=PIPE)
            ret = p2.communicate()
        rm_eff(path)

        if p2.returncode != 0:
            print("Error processing %s:" % path)
            if ret[1]:
                for line in ret[1].splitlines():
                    print(line)
            # We couldn't decompress this, so there's no value in trying again.
            try:
                swift_client.delete_object(bucket, uuid)
            except swiftclient.client.ClientException as e:
                if "404 Not Found" in str(e):
                    rm_eff(core_file)
                    continue
            print("Removed corrupt core %s from swift" % (uuid))
            unqueued_count += 1
            rm_eff(core_file)
            continue
        # confirm that gdb thinks the core file is good
        gdb_cmd = [gdb_path, "--batch", "--ex", "target core %s" % core_file]
        proc = Popen(gdb_cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True, errors="replace")
        (out, err) = proc.communicate()
        if "is truncated: expected core file size" in err or "not a core dump" in err:
            # Not a core file, there's no value in trying again.
            try:
                swift_client.delete_object(bucket, uuid)
            except swiftclient.client.ClientException as e:
                if "404 Not Found" in str(e):
                    rm_eff(core_file)
                    continue
            print("Removed corrupt core %s from swift" % (uuid))
            unqueued_count += 1
        else:
            print("Core %s is good" % (uuid))
        rm_eff(core_file)
    print("Finished, reviewed %i cores, removed %i cores." % (count, unqueued_count))
