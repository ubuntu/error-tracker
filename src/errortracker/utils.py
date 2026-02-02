import logging
import re

import apt

from errortracker import oopses

EOL_RELEASES = {
    "Ubuntu 10.04": "lucid",
    "Ubuntu 10.10": "maverick",
    "Ubuntu 11.04": "natty",
    "Ubuntu 11.10": "oneiric",
    "Ubuntu 12.04": "precise",
    "Ubuntu 12.10": "quantal",
    "Ubuntu 13.04": "raring",
    "Ubuntu 13.10": "saucy",
    "Ubuntu 14.04": "trusty",
    "Ubuntu RTM 14.09": "vivid",
    "Ubuntu 14.10": "utopic",
    "Ubuntu 15.04": "vivid",
    "Ubuntu 15.10": "wily",
    "Ubuntu 16.04": "xenial",
    "Ubuntu 16.10": "yakkety",
    "Ubuntu 17.04": "zesty",
    "Ubuntu 17.10": "artful",
    "Ubuntu 18.04": "bionic",
    "Ubuntu 18.10": "cosmic",
    "Ubuntu 19.04": "disco",
    "Ubuntu 19.10": "eoan",
    "Ubuntu 20.10": "groovy",
    "Ubuntu 21.04": "hirsute",
    "Ubuntu 21.10": "impish",
    "Ubuntu 22.10": "kinetic",
    "Ubuntu 23.04": "lunar",
    "Ubuntu 23.10": "mantic",
    "Ubuntu 24.10": "oracular",
    "Ubuntu 25.04": "plucky",
}


def get_fields_for_bucket_counters(problem_type, release, package, version, pkg_arch):
    fields = []
    if release:
        if package and version:
            fields.append("%s:%s:%s" % (release, package, version))
            fields.append("%s:%s" % (release, package))
            fields.append(release)
            fields.append("%s:%s" % (package, version))
            fields.append(package)
            if pkg_arch:
                fields.append("%s:%s:%s:%s" % (release, package, version, pkg_arch))
                fields.append("%s:%s:%s" % (release, package, pkg_arch))
                fields.append("%s:%s" % (release, pkg_arch))
                fields.append("%s:%s:%s" % (package, version, pkg_arch))
                fields.append("%s:%s" % (package, pkg_arch))
                fields.append("%s" % pkg_arch)
        else:
            fields.append(release)
            # package w/o version is somewhat useful, version w/o package
            # isn't so only record this counter
            if package:
                fields.append("%s:%s" % (release, package))
                fields.append(package)
            if pkg_arch:
                fields.append("%s:%s" % (release, pkg_arch))
                fields.append("%s" % pkg_arch)
    elif package and version:
        fields.append("%s:%s" % (package, version))
        fields.append("%s" % (package))
        if pkg_arch:
            fields.append("%s:%s:%s" % (package, version, pkg_arch))
            fields.append("%s:%s" % (package, pkg_arch))
            fields.append("%s" % pkg_arch)

    if problem_type:
        fields.extend(["%s:%s" % (problem_type, field) for field in fields])
    return fields


def split_package_and_version(package):
    if not package:
        return ("", "")
    s = package.split()[:2]
    if len(s) == 2:
        package, version = s
    else:
        package, version = (package, "")
    if version == "(not":
        # The version is set to '(not installed)'
        version = ""
    return (package, version)


def get_package_architecture(report_dict):
    # return the system arch if the package is arch all
    pkg_arch = report_dict.get("PackageArchitecture", "")
    if pkg_arch == "all":
        arch = report_dict.get("Architecture", "")
        pkg_arch = arch
    elif pkg_arch == "unknown":
        pkg_arch = ""
    return pkg_arch


def format_crash_signature(crash_signature) -> str:
    # https://errors.ubuntu.com/oops-local/2013-03-07/50428.daisy.ubuntu.com3
    # Exception-Value: InvalidRequestException(why='Key length of 127727 is
    # longer than maximum of 65535')
    # We use 32768 rather than 65535 to provide padding when the bucket ID
    # forms part of a composite key, as it does in daybuckets.
    if not crash_signature:
        return ""

    # Translate back to unicode so we can correctly slice this.
    if type(crash_signature) is bytes:
        crash_signature = crash_signature.decode("utf-8")

    crash_signature = crash_signature[:32768]

    return crash_signature


def bucket(oops_id, crash_signature, report_dict):
    release = report_dict.get("DistroRelease", "")
    package = report_dict.get("Package", "")
    src_package = report_dict.get("SourcePackage", "")
    problem_type = report_dict.get("ProblemType", "")
    system_uuid = report_dict.get("SystemIdentifier", "")

    version = None
    if package:
        package, version = split_package_and_version(package)
    pkg_arch = get_package_architecture(report_dict)

    automated_testing = False
    if system_uuid.startswith("deadbeef"):
        automated_testing = True

    if automated_testing:
        fields = None
    else:
        fields = get_fields_for_bucket_counters(problem_type, release, package, version, pkg_arch)
    if version:
        oopses.update_bucket_systems(crash_signature, system_uuid, version=version)
    # DayBucketsCount is only added to if fields is not None, so set fields to
    # None for crashes from systems running automated tests.
    oopses.bucket(oops_id, crash_signature, fields)

    oopses.update_bucket_hashes(crash_signature)

    # BucketMetadata is displayed on the main page and shouldn't include
    # derivative or custom releases, so don't write them to the table.
    release_re = re.compile(r"^Ubuntu \d\d.\d\d$")
    if (src_package and package and version) and release_re.match(release):
        oopses.update_bucket_metadata(
            crash_signature,
            package,
            version,
            apt.apt_pkg.version_compare,
            release,
        )
        oopses.update_bucket_versions_count(crash_signature, release, version)
        oopses.update_source_version_buckets(src_package, version, crash_signature)


def retraceable_release(release):
    if release in EOL_RELEASES:
        logging.info("%s is EoL, not retraceable", release)
        return False
    derivative_re = re.compile(r"^Ubuntu( RTM| Kylin)? \d\d.\d\d$")
    if derivative_re.match(release):
        return True
    else:
        logging.info("%s doesn't match %s, not retraceable", release, derivative_re)
        return False


def retraceable_package(package):
    if "[origin: " not in package:
        return True
    elif "[origin: Ubuntu RTM]" in package:
        return True
    # confirm how this can happen
    # elif "[origin: Ubuntu]" in package:
    #     return True
    elif "[origin: LP-PPA-ci-train-ppa-service" in package:
        return True
    else:
        return False


def blocklisted_device(system_token):
    """Return True if a device is not allowed to report crashes.

    Used for devices that have repeatedly failed to submit a crash.
    """

    blocklist = []
    if system_token in blocklist:
        return True
    return False
