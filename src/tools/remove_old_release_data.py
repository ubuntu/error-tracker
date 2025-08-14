#!/usr/bin/python3

import os
import sys
from datetime import datetime, timedelta
from time import sleep

import distro_info
from cassandra import ConsistencyLevel, OperationTimedOut
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, NoHostAvailable

from daisy import config

auth_provider = PlainTextAuthProvider(
    username=config.cassandra_username, password=config.cassandra_password
)
cluster = Cluster(config.cassandra_hosts, auth_provider=auth_provider)
session = cluster.connect(config.cassandra_keyspace)
session.default_consistency_level = ConsistencyLevel.LOCAL_ONE
oops_lookup_stmt = session.prepare('SELECT * FROM "OOPS" WHERE key=?')
oops_delete_stmt = session.prepare('DELETE FROM "OOPS" WHERE key=? AND column1=?')

URL = "https://errors.ubuntu.com/oops/"

# 2022-02-16 generate this list by looking at apport package hooks for things
# to delete
unneeded_columns = (
    "Disassembly",
    "ProcMaps",
    "ProcStatus",
    "Registers",
    "StacktraceTop",
    "Lsusb",
    "CrashReports",
    "HookError_source_nautilus",
    "HookError_source_totem",
    "RelatedPackageVersions",
    "HotSpotError",
    "CrashDB",
    "DpkgHistoryLog.txt",
    "DpkgTerminalLog.txt",
    "Dependencies",
    "UserGroups",
    "UpgradeStatus",
    "JournalErrors",
    "Desktop-Session",
    "Env",
    "InstalledPlugins",
    "Load-Avg-1min",
    "Load-Processes-Running-Percent",
    "DiskUsage",
    "DRM.card0-DVI-D-1",
    "DRM.card0-DVI-I-1",
    "etcconfigc00example",
    "dmi.bios.date",
    "dmi.bios.vendor",
    "dmi.bios.version",
    "dmi.board.asset.tag",
    "dmi.board.name",
    "dmi.board.vendor",
    "dmi.chassis.type",
    "dmi.chassis.vendor",
    "dmi.modalias",
    "dmi.product.family",
    "dmi.product.name",
    "dmi.product.sku",
    "dmi.product.version",
    "dmi.sys.vendor",
    "CurrentDmesg",
    # alsa
    "UserAsoundrc",
    "UserAsoundrcAsoundconf",
    "AlsaVersion",
    "AlsaDevices",
    "AplayDevices",
    "ArecordDevices",
    "PciMultimedia",
    "AlsaInfo",
    "AudioDevicesInUse",
    "PulseList",
    "PaInfo",
    # hookutils
    "ProcInterrupts",
    "Lspci",
    "Lspci-vt",
    "Lsusb-v",
    "Lsusb-t",
    "ProcModules",
    "UdevDb",
    "acpidump",
    "Prtconf",
    "PccardctlStatus",
    "PccardctlIdent",
    "GsettingsChanges",
    "IpRoute",
    "IpAddr",
    "PciNetwork",
    "IfupdownConfig",
    "WifiSyslog",
    "IwConfig",
    "RfKill",
    "CRDA",
    "WpaSupplicantLog",
    "Papersize",
    "CupsErrorLog",
    "Locale",
    "Lpstat",
    "PpdFiles",
    "PrintingPackages",
    "KernLog",
    "AuditLog",
)


def check_and_remove_oops(oopsid):
    data = {}
    max_retries = 5
    for i in range(max_retries):
        period = 30 + (30 * i)
        try:
            oops_data = session.execute(oops_lookup_stmt, [oopsid.encode()])
        except (OperationTimedOut, NoHostAvailable):
            print(("Sleeping %ss as we timed out when querying." % period))
            sleep(period)
            continue
        else:
            break
    else:
        print(("Cassandra operation timed out %s times." % max_retries))
        return
    # all the column "names" are column1 so make a dictionary of keys: values
    for od in oops_data:
        data[od.column1] = od.value
    # just double check that its the right release
    if data.get("DistroRelease", "") == rname:
        if data.get("ProcMaps", "") == "":
            # print("Skipping already cleaned crash.")
            return
        for column in unneeded_columns:
            for i in range(max_retries):
                period = 30 + (30 * i)
                try:
                    session.execute(oops_delete_stmt, [oopsid.encode(), "%s" % column])
                except (OperationTimedOut, NoHostAvailable):
                    print(("Sleeping %ss as we timed out when deleting." % period))
                    sleep(period)
                    continue
                else:
                    break
            else:
                print(("Cassandra operation timed out %s times." % max_retries))
                return
        print(("%s%s was from %s and had its data removed" % (URL, oopsid, rname)))


# Main
if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        dry_run = True
        sys.argv.remove("--dry-run")
    else:
        dry_run = False

    codename = sys.argv[1]

    di = distro_info.UbuntuDistroInfo()
    release = [r for r in di.get_all("object") if r.series == codename][0]
    # strip out "LTS"
    rname = "Ubuntu %s" % release.version.split()[0]

    open_date = release.created
    eol_date = release.eol

    # use restart_date if you have to stop and start the job again
    restart_date = ""
    if restart_date:
        open_date = datetime.strptime(restart_date, "%Y-%m-%d").date()

    delta = eol_date - open_date

    for i in range(delta.days + 1):
        current_date = open_date + timedelta(days=i)

        removal_progress = "%s-remove_old_%s_data.txt" % (
            current_date,
            rname.split(" ")[-1],
        )
        if os.path.exists(removal_progress):
            with open(removal_progress, "r") as f:
                last_row = f.readline()
        else:
            last_row = ""

        run = 1
        if last_row == "":
            r_oopses = session.execute(
                'SELECT * FROM "ErrorsByRelease" '
                "WHERE key = '%s' "
                "AND key2 = '%s' LIMIT 5000" % (rname, current_date)
            )
            print(("%s %s run: %s" % (rname, current_date, run)))
            for r_oops_row in r_oopses:
                check_and_remove_oops(str(r_oops_row.column1))
                last_row = str(r_oops_row.column1)
            run += 1

        if last_row == "":
            continue

        while run < 150:
            r_oopses2 = session.execute(
                'SELECT * FROM "ErrorsByRelease" '
                "WHERE key = '%s' "
                "AND key2 = '%s' AND column1 > %s "
                "LIMIT 5000" % (release, current_date, last_row)
            )
            print(("%s %s run: %s" % (rname, current_date, run)))
            r_oops_row = ""
            for r_oops_row in r_oopses2:
                check_and_remove_oops(str(r_oops_row.column1))
                last_row = str(r_oops_row.column1)
            if r_oops_row:
                with open(removal_progress, "w") as f:
                    f.write(str(r_oops_row.column1))
            else:
                if os.path.exists(removal_progress):
                    os.unlink(removal_progress)
                break
            run += 1
