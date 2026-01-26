#!/usr/bin/python3

import sys

import distro_info
from cassandra import OperationTimedOut
from cassandra.cluster import NoHostAvailable
from tenacity import retry, retry_if_exception_type, wait_exponential

from errortracker import cassandra, cassandra_schema

cassandra.setup_cassandra()

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
    "ShellJournal",
    "JournalAll",
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


@retry(
    wait=wait_exponential(), retry=retry_if_exception_type((OperationTimedOut, NoHostAvailable))
)
def check_and_remove_oops(oopsid):
    oops_data = cassandra_schema.OOPS.get_as_dict(key=oopsid.encode())
    if oops_data.get("DistroRelease", "") == release_name:
        if oops_data.get("Date", "") == "":
            print(("%s%s was skipped (already cleaned)" % (URL, oopsid)))
            return
        for column in unneeded_columns:
            cassandra_schema.OOPS.filter(key=oopsid.encode(), column1=column).delete()
        print(("%s%s was from %s and had its data removed" % (URL, oopsid, release_name)))
    else:
        print(
            ("%s%s was from %s and was kept" % (URL, oopsid, oops_data.get("DistroRelease", "")))
        )


if __name__ == "__main__":
    codename = sys.argv[1]

    di = distro_info.UbuntuDistroInfo()
    release = [r for r in di.get_all("object") if r.series == codename][0]
    # strip out "LTS"
    release_name = "Ubuntu %s" % release.version.split()[0]

    for row in cassandra_schema.ErrorsByRelease.filter(key=release_name).allow_filtering().all():
        check_and_remove_oops(str(row.column1))
        row.delete()
