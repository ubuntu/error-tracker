#!/usr/bin/python3

# Dump and or delete all the crash reports from a specific systemid like
# https://errors.ubuntu.com/user/cfc8a68e9841db904b074a1135c3e6514ac806e675445489d5ad3aa09633fe2d968c6918cb9f343f2c7a353461ab93afcbccf176af756b7426f75935afc64cb2
import io
import json
import sys
import tarfile
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import swiftclient
from problem_report import CompressedValue, _base64_decoder

sys.path.insert(0, str(Path(__file__).parent.parent))

from errors import cassie
from errortracker import cassandra, config
from errortracker.cassandra_schema import OOPS, Stacktrace, UserOOPS
from errortracker.swift_utils import get_swift_client

cassandra.setup_cassandra()
swift = get_swift_client()
now = datetime.now()


def parse_args():
    parser = ArgumentParser(description="GDPR request handler for the Error Tracker")
    parser.add_argument(
        "--no-dump",
        action="store_true",
        help="Do not generate an archive tarball of the data associated with this whoopsie ID",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Delete all the data associated with this whoopsie ID",
    )
    parser.add_argument(
        "whoopsie_id",
        help="The whoopsie ID to handle data for",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.no_dump:
        dump(args.whoopsie_id)

    if args.remove:
        remove(args.whoopsie_id)


def dump(whoopsie_id):
    print(f"Dumping data for {whoopsie_id} as of {now}")
    with tarfile.open(
        f"error-tracker-{whoopsie_id}-{now.isoformat(timespec='seconds')}.tar.gz",
        "w|gz",
    ) as tar:
        oopses = UserOOPS.objects.filter(key=whoopsie_id.encode())
        for oops in oopses:
            oopsid = oops.column1

            oops = cassie.get_crash(oopsid)
            print(f"Handling OOPS {oopsid}")

            # Handle bucket information
            if "StacktraceAddressSignature" in oops:
                sas = oops["StacktraceAddressSignature"].encode()
                oops["Stacktrace"] = (
                    Stacktrace.objects.filter(key=sas, column1="Stacktrace")
                    .values_list("value", flat=True)
                    .first()
                )
                oops["ThreadStacktrace"] = (
                    Stacktrace.objects.filter(key=sas, column1="ThreadStacktrace")
                    .values_list("value", flat=True)
                    .first()
                )
                print(f"  Added Stacktrace and ThreadStacktrace for OOPS {oopsid}")

            # save OOPS data in tarball
            json_bytes = json.dumps(oops).encode("utf-8")
            tarinfo = tarfile.TarInfo(name=f"oops/{oopsid}.json")
            tarinfo.size = len(json_bytes)
            tar.addfile(tarinfo, io.BytesIO(json_bytes))

            # handle possible core file still around
            try:
                tarinfo = tarfile.TarInfo(name=f"cores/{oopsid}.core")
                _, body = swift.get_object(config.swift_bucket, oopsid, resp_chunk_size=65536)
                compressed_core_bytes = io.BytesIO()
                for chunk in body:
                    compressed_core_bytes.write(chunk)
                compressed_core_bytes.seek(0)
                core_bytes = io.BytesIO()
                for block in CompressedValue.decode_compressed_stream(
                    _base64_decoder(compressed_core_bytes)
                ):
                    core_bytes.write(block)
                core_bytes.seek(0)
                tarinfo.size = core_bytes.getbuffer().nbytes
                tar.addfile(tarinfo, core_bytes)
                print(f"  Added core for OOPS {oopsid}")
            except swiftclient.exceptions.ClientException as e:
                if "404 Not Found" in str(e):
                    pass
                else:
                    raise e


def remove(whoopsie_id):
    print(f"Removing data for {whoopsie_id} as of {now}")
    oopses = UserOOPS.objects.filter(key=whoopsie_id.encode())
    for oops in oopses:
        oopsid = oops.column1

        oops = cassie.get_crash(oopsid)
        if "StacktraceAddressSignature" in oops:
            sas = oops["StacktraceAddressSignature"].encode()
            Stacktrace.objects.filter(key=sas, column1="Stacktrace").delete()
            Stacktrace.objects.filter(key=sas, column1="ThreadStacktrace").delete()
            print(f"Deleted Stacktrace and ThreadStacktrace for {sas}")

        try:
            swift.delete_object(config.swift_bucket, oopsid)
            print(f"Deleted core from swift {oopsid}")
        except swiftclient.exceptions.ClientException as e:
            if "404 Not Found" in str(e):
                pass
            else:
                raise e

        OOPS.objects.filter(key=oopsid.encode()).delete()
        print(f"Deleted OOPS {oopsid}")

    UserOOPS.objects.filter(key=whoopsie_id.encode()).delete()
    print(f"Deleted UserOOPSes for {whoopsie_id}")


if __name__ == "__main__":
    main()
